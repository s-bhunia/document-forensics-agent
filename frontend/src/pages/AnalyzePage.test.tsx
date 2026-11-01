import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnalyzePage } from "./AnalyzePage";
import { renderWithProviders } from "../test/utils";
import { jsonResponse, summaryFixture } from "../test/fixtures";
import * as client from "../api/client";

function setup() {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(jsonResponse({ items: [summaryFixture], total: 1, page: 1, page_size: 5 }))),
  );
  const user = userEvent.setup({ applyAccept: false });
  renderWithProviders(<AnalyzePage />);
  const input = screen.getByTestId("file-input") as HTMLInputElement;
  return { user, input };
}

function makeFile(name: string, size: number, type = "") {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("AnalyzePage upload flow", () => {
  it("shows an inline error for unsupported file types", async () => {
    const { user, input } = setup();
    await user.upload(input, makeFile("notes.txt", 100, "text/plain"));
    expect(screen.getByRole("alert")).toHaveTextContent(/unsupported file type ".txt"/i);
    expect(screen.queryByRole("button", { name: /^Analyze$/ })).toBeNull();
  });

  it("shows an inline error for files over 25 MB", async () => {
    const { user, input } = setup();
    await user.upload(input, makeFile("big.pdf", 26 * 1024 * 1024, "application/pdf"));
    expect(screen.getByRole("alert")).toHaveTextContent(/too large/i);
  });

  it("validates dropped files too", () => {
    setup();
    const zone = screen.getByRole("button", { name: /choose documents/i });
    fireEvent.drop(zone, { dataTransfer: { files: [makeFile("clip.mp4", 100, "video/mp4")] } });
    expect(screen.getByRole("alert")).toHaveTextContent(/unsupported/i);
  });

  it("accepts a valid file, uploads it and navigates to the analysis", async () => {
    const upload = vi.spyOn(client, "uploadAnalysis").mockImplementation(async (_file, onProgress) => {
      onProgress?.(0.5);
      return { ...summaryFixture, id: "new-id", status: "queued" };
    });
    const { user, input } = setup();
    await user.upload(input, makeFile("receipt.jpg", 2048, "image/jpeg"));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("receipt.jpg")).toBeInTheDocument();
    expect(screen.getByText("2 KB")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Analyze$/ }));
    expect(upload).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("other route")).toBeInTheDocument();
  });

  it("shows the server error when the upload is rejected", async () => {
    vi.spyOn(client, "uploadAnalysis").mockRejectedValue(new client.ApiError("Unsupported file", 400));
    const { user, input } = setup();
    await user.upload(input, makeFile("scan.png", 2048, "image/png"));
    await user.click(screen.getByRole("button", { name: /^Analyze$/ }));
    expect(await screen.findByText("Unsupported file")).toBeInTheDocument();
  });

  it("lists recent analyses", async () => {
    setup();
    expect(await screen.findByRole("link", { name: "payslip-march.png" })).toBeInTheDocument();
  });
});
