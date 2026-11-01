import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FindingsList } from "./FindingsList";
import { numberFindings } from "../lib/findings";
import { completedFixture } from "../test/fixtures";

const findings = numberFindings(completedFixture.result!.findings);

function setup(selectedId: string | null = null) {
  const onSelect = vi.fn();
  const onShowOnPage = vi.fn();
  render(<FindingsList findings={findings} selectedId={selectedId} onSelect={onSelect} onShowOnPage={onShowOnPage} />);
  const list = () => screen.getByRole("list", { name: "Findings list" });
  return { onSelect, onShowOnPage, list, user: userEvent.setup() };
}

describe("FindingsList", () => {
  it("renders all findings with number, title, quoted text and evidence", () => {
    const { list } = setup();
    expect(within(list()).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText("Font mismatch in net pay")).toBeInTheDocument();
    expect(screen.getByText("“4,250.00”")).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "Font distance" })).toBeInTheDocument();
    expect(screen.getByText("0.431")).toBeInTheDocument();
  });

  it("filters by severity and clears filters", async () => {
    const { list, user } = setup();
    await user.click(screen.getByRole("button", { name: /^High/ }));
    expect(within(list()).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByText("Font mismatch in net pay")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Low/ }));
    expect(within(list()).getAllByRole("listitem")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(within(list()).getAllByRole("listitem")).toHaveLength(3);
  });

  it("filters by category", async () => {
    const { list, user } = setup();
    await user.selectOptions(screen.getByLabelText("Filter by category"), "metadata");
    const items = within(list()).getAllByRole("listitem");
    expect(items).toHaveLength(1);
    expect(within(items[0]).getByText("Edited with image software")).toBeInTheDocument();
  });

  it("calls onSelect when a finding is clicked", async () => {
    const { onSelect, user } = setup();
    await user.click(screen.getByText("Local compression anomaly"));
    expect(onSelect).toHaveBeenCalledWith("f3");
  });

  it("only offers 'Show on page' for located findings", async () => {
    const { onShowOnPage, user } = setup();
    const buttons = screen.getAllByRole("button", { name: "Show on page" });
    expect(buttons).toHaveLength(2);
    expect(within(screen.getByTestId("finding-f2")).queryByRole("button", { name: "Show on page" })).toBeNull();
    await user.click(within(screen.getByTestId("finding-f1")).getByRole("button", { name: "Show on page" }));
    expect(onShowOnPage).toHaveBeenCalledWith("f1");
  });

  it("tags agent findings that were not grounded by measurement and hides meta evidence keys", () => {
    setup();
    const ungrounded = screen.getByTestId("finding-f3");
    expect(within(ungrounded).getByText("Not verified by measurement")).toBeInTheDocument();
    expect(within(ungrounded).queryByRole("table")).toBeNull();
    expect(within(ungrounded).queryByText("Source")).toBeNull();
    expect(within(ungrounded).queryByText("Grounded")).toBeNull();
    expect(within(screen.getByTestId("finding-f1")).queryByText("Not verified by measurement")).toBeNull();
  });

  it("marks the selected finding", () => {
    setup("f2");
    expect(screen.getByTestId("finding-f2")).toHaveAttribute("data-selected", "true");
    expect(screen.getByTestId("finding-f1")).not.toHaveAttribute("data-selected");
  });
});
