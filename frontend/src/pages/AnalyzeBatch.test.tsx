import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnalyzePage } from "./AnalyzePage";
import { renderWithProviders } from "../test/utils";
import { jsonResponse, summaryFixture } from "../test/fixtures";
import * as client from "../api/client";
import type { AnalysisDetail } from "../api/types";
import { BATCH_STORAGE_KEY } from "../hooks/useBatch";
import { UPLOAD_CONCURRENCY } from "../hooks/useUploadQueue";
import { MAX_BATCH_FILES } from "../lib/fileValidation";

function makeFile(name: string, size = 2048, type = "image/png") {
  const file = new File(["x"], name, { type, lastModified: 1 });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

const detail = (id: string, over: Partial<AnalysisDetail> = {}): AnalysisDetail => ({
  ...summaryFixture,
  id,
  filename: `${id}.png`,
  result: null,
  ...over,
});

function stubApi(detailFor: (id: string) => AnalysisDetail = (id) => detail(id)) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const m = url.match(/\/api\/analyses\/([^/?]+)$/);
    if (m) return Promise.resolve(jsonResponse(detailFor(decodeURIComponent(m[1]))));
    return Promise.resolve(jsonResponse({ items: [], total: 0, page: 1, page_size: 5 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function setup() {
  const user = userEvent.setup({ applyAccept: false });
  renderWithProviders(<AnalyzePage />);
  return { user, input: screen.getByTestId("file-input") as HTMLInputElement };
}

describe("AnalyzePage multi-file upload", () => {
  it("shows the per-file note under the dropzone", () => {
    stubApi();
    setup();
    expect(screen.getByText("Each file is analysed separately.")).toBeInTheDocument();
  });

  it("keeps valid files and lists invalid ones with their reason", async () => {
    stubApi();
    const { user, input } = setup();
    await user.upload(input, [
      makeFile("a.png"),
      makeFile("notes.txt", 10, "text/plain"),
      makeFile("b.pdf", 26 * 1024 * 1024, "application/pdf"),
      makeFile("c.jpg"),
    ]);

    expect(screen.getAllByTestId("selected-file")).toHaveLength(2);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("2 files were not added");
    expect(alert).toHaveTextContent(/notes\.txt: Unsupported file type/);
    expect(alert).toHaveTextContent(/b\.pdf: File is too large/);
    expect(screen.getByRole("button", { name: /Analyze 2 files/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove a.png" }));
    expect(screen.getAllByTestId("selected-file")).toHaveLength(1);
  });

  it(`caps a batch at ${MAX_BATCH_FILES} files`, async () => {
    stubApi();
    const { user, input } = setup();
    const files = Array.from({ length: MAX_BATCH_FILES + 2 }, (_, i) => makeFile(`page-${i}.png`));
    await user.upload(input, files);
    expect(screen.getAllByTestId("selected-file")).toHaveLength(MAX_BATCH_FILES);
    expect(screen.getByRole("alert")).toHaveTextContent(`Only ${MAX_BATCH_FILES} files can be analyzed at once.`);

    await user.upload(input, [makeFile("extra.png")]);
    expect(screen.getAllByTestId("selected-file")).toHaveLength(MAX_BATCH_FILES);
    expect(screen.getByRole("alert")).toHaveTextContent("extra.png");
  });

  it(`uploads ${UPLOAD_CONCURRENCY} at a time, isolates a failure and allows retry`, async () => {
    stubApi();
    let inFlight = 0;
    let maxInFlight = 0;
    let badAttempts = 0;
    const upload = vi.spyOn(client, "uploadAnalysis").mockImplementation(async (file, onProgress) => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      onProgress?.(0.5);
      await new Promise((r) => setTimeout(r, 20));
      inFlight -= 1;
      if (file.name === "bad.png" && badAttempts++ === 0) throw new client.ApiError("File is corrupt", 400);
      return { ...summaryFixture, id: file.name.replace(".png", ""), filename: file.name, status: "queued" };
    });

    const { user, input } = setup();
    const names = ["f1.png", "f2.png", "bad.png", "f3.png", "f4.png", "f5.png", "f6.png"];
    await user.upload(input, names.map((n) => makeFile(n)));
    await user.click(screen.getByRole("button", { name: /Analyze 7 files/ }));

    expect(await screen.findByText("File is corrupt")).toBeInTheDocument();
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(7));
    expect(maxInFlight).toBe(UPLOAD_CONCURRENCY);

    await waitFor(() => expect(screen.getAllByTestId("selected-file")).toHaveLength(1));
    expect(screen.getByTestId("selected-file")).toHaveAttribute("data-state", "failed");

    const batch = screen.getByRole("list", { name: "Batch analyses" });
    expect(within(batch).getAllByRole("listitem")).toHaveLength(6);
    expect(JSON.parse(window.sessionStorage.getItem(BATCH_STORAGE_KEY)!)).toHaveLength(6);

    await waitFor(() => expect(screen.getByRole("button", { name: "Retry bad.png" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Retry bad.png" }));
    await waitFor(() => expect(screen.queryAllByTestId("selected-file")).toHaveLength(0));
    expect(upload).toHaveBeenCalledTimes(8);
    expect(within(batch).getAllByRole("listitem")).toHaveLength(7);
    expect(await within(batch).findByRole("link", { name: "bad.png" })).toHaveAttribute("href", "/analyses/bad");
  });

  it("polls the batch until every analysis is finished", async () => {
    window.sessionStorage.setItem(BATCH_STORAGE_KEY, JSON.stringify(["one", "two"]));
    let oneCalls = 0;
    const fetchMock = stubApi((id) => {
      if (id === "one") {
        oneCalls += 1;
        return oneCalls === 1
          ? detail("one", { status: "processing", label: null, risk_score: null })
          : detail("one", { status: "completed", label: "highly_risky", risk_score: 0.91 });
      }
      return detail("two", { status: "failed", label: null, risk_score: null, error: "Unreadable PDF" });
    });
    setup();

    const progress = await screen.findByTestId("batch-progress");
    await waitFor(() => expect(progress).toHaveTextContent("1 of 2 finished"));
    expect(within(screen.getByTestId("batch-row-one")).getByText("Processing")).toBeInTheDocument();
    expect(within(screen.getByTestId("batch-row-two")).getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText(/Unreadable PDF/)).toBeInTheDocument();

    await waitFor(() => expect(progress).toHaveTextContent("All 2 finished"), { timeout: 5000 });
    expect(within(screen.getByTestId("batch-row-one")).getByText(/Highly risky/)).toHaveTextContent("91%");
    const callsForTwo = fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/analyses/two")).length;
    expect(callsForTwo).toBe(1);
  });

  it("restores the batch from sessionStorage and clears it", async () => {
    window.sessionStorage.setItem(BATCH_STORAGE_KEY, JSON.stringify(["one"]));
    stubApi((id) => detail(id, { status: "completed", label: "likely_authentic", risk_score: 0.05 }));
    const { user } = setup();
    expect(await screen.findByRole("link", { name: "one.png" })).toHaveAttribute("href", "/analyses/one");
    await user.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.queryByRole("list", { name: "Batch analyses" })).toBeNull();
    expect(window.sessionStorage.getItem(BATCH_STORAGE_KEY)).toBeNull();
  });
});
