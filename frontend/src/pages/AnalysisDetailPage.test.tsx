import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnalysisDetailPage } from "./AnalysisDetailPage";
import { renderWithProviders } from "../test/utils";
import { completedFixture, jsonResponse, queuedFixture } from "../test/fixtures";

function mockFetch(handler: (url: string) => Response | Promise<Response>) {
  const fn = vi.fn((input: RequestInfo | URL) => Promise.resolve(handler(String(input))));
  vi.stubGlobal("fetch", fn);
  return fn;
}

const renderDetail = (id: string) =>
  renderWithProviders(<AnalysisDetailPage />, { route: `/analyses/${id}`, path: "/analyses/:id" });

describe("AnalysisDetailPage", () => {
  it("renders a completed result", async () => {
    const fetchMock = mockFetch(() => jsonResponse(completedFixture));
    renderDetail("a1");

    expect(await screen.findByRole("heading", { name: "payslip-march.png" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/analyses/a1", expect.anything());

    expect(screen.getAllByText("Suspicious").length).toBeGreaterThan(0);
    expect(screen.getByRole("meter", { name: "Risk score" })).toHaveAttribute("aria-valuenow", "72");
    expect(screen.getByText("AI investigation")).toBeInTheDocument();
    expect(screen.getByTestId("usage-chip")).toHaveTextContent("≈ $0.08 / page");
    expect(screen.getByText(/retyped in a different font/)).toBeInTheDocument();
    expect(screen.getByTestId("count-high")).toHaveTextContent("1");
    expect(screen.getByTestId("count-medium")).toHaveTextContent("1");
    expect(screen.getByTestId("count-low")).toHaveTextContent("1");
    expect(screen.getByTestId("count-info")).toHaveTextContent("0");
    expect(screen.getByText(/Image · 2 pages/)).toBeInTheDocument();
    expect(screen.getByText("Adobe Photoshop 25.0", { selector: "dd" })).toBeInTheDocument();

    expect(screen.getByAltText("Page 1")).toBeInTheDocument();
    expect(screen.getByTestId("box-f1")).toBeInTheDocument();
    expect(screen.getByText("Copy-move detection")).toBeInTheDocument();
  });

  it("'Show on page' switches page and highlights the box", async () => {
    mockFetch(() => jsonResponse(completedFixture));
    renderDetail("a1");
    const user = userEvent.setup();
    const card = await screen.findByTestId("finding-f3");
    await user.click(within(card).getByRole("button", { name: "Show on page" }));
    expect(screen.getByAltText("Page 2")).toBeInTheDocument();
    expect(screen.getByTestId("box-f3")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("finding-f3")).toHaveAttribute("data-selected", "true");
  });

  it("selecting a box highlights the finding card", async () => {
    mockFetch(() => jsonResponse(completedFixture));
    renderDetail("a1");
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("box-f1"));
    expect(screen.getByTestId("finding-f1")).toHaveAttribute("data-selected", "true");
  });

  it("shows extracted text in its tab", async () => {
    mockFetch(() => jsonResponse(completedFixture));
    renderDetail("a1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: /Extracted text/ }));
    expect(screen.getByText("ACME Corp payslip")).toBeInTheDocument();
  });

  it("shows the investigation timeline in its own tab", async () => {
    mockFetch(() => jsonResponse(completedFixture));
    renderDetail("a1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: "Investigation" }));
    expect(screen.getByText("claude-vision-test")).toBeInTheDocument();
    expect(screen.getAllByTestId("investigation-step")).toHaveLength(4);
    expect(screen.getByText("Zoomed into region")).toBeInTheDocument();
  });

  it("hides the investigation tab and shows a rule-based tag when there is no investigation", async () => {
    const result = { ...completedFixture.result!, investigation: null, summary_source: "rules" as const };
    mockFetch(() => jsonResponse({ ...completedFixture, result }));
    renderDetail("a1");
    expect(await screen.findByRole("tab", { name: "Review" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Investigation" })).toBeNull();
    expect(screen.getByText("Rule-based")).toBeInTheDocument();
    expect(screen.queryByText("AI investigation")).toBeNull();
    expect(screen.queryByTestId("usage-chip")).toBeNull();
  });

  it("shows the failed-investigation notice in the header and the tab", async () => {
    const result = {
      ...completedFixture.result!,
      summary_source: "rules" as const,
      investigation: { error: "Model timed out after 240 s", usage: null },
    };
    mockFetch(() => jsonResponse({ ...completedFixture, result }));
    renderDetail("a1");
    const user = userEvent.setup();
    expect(await screen.findByText(/AI investigation failed — showing rule-based result/)).toBeInTheDocument();
    expect(screen.getByText("Model timed out after 240 s")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Investigation" }));
    expect(screen.getAllByText(/AI investigation failed/)).toHaveLength(2);
    expect(screen.queryByTestId("investigation-step")).toBeNull();
  });

  it("shows the processing state while queued and polls until completed", async () => {
    let calls = 0;
    const fetchMock = mockFetch(() => {
      calls += 1;
      return jsonResponse(calls < 2 ? queuedFixture : { ...completedFixture, id: "q1" });
    });
    renderDetail("q1");

    expect(await screen.findByRole("heading", { name: "Waiting in queue" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Analysis progress" })).toBeInTheDocument();

    await waitFor(() => expect(screen.getByRole("heading", { name: "payslip-march.png" })).toBeInTheDocument(), {
      timeout: 4000,
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("shows the failure message with a retry link", async () => {
    mockFetch(() =>
      jsonResponse({ ...queuedFixture, status: "failed", error: "PDF is encrypted" }),
    );
    renderDetail("q1");
    expect(await screen.findByText("PDF is encrypted")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Upload again/ })).toHaveAttribute("href", "/");
  });

  it("shows a not-found state on 404", async () => {
    mockFetch(() => jsonResponse({ detail: "Not found" }, 404));
    renderDetail("missing");
    expect(await screen.findByRole("heading", { name: "Analysis not found" })).toBeInTheDocument();
  });
});
