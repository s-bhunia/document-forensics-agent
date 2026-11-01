import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PageViewer } from "./PageViewer";
import { numberFindings } from "../lib/findings";
import { completedFixture } from "../test/fixtures";

const result = completedFixture.result!;
const findings = numberFindings(result.findings);

function setup(currentPage = 1, selectedId: string | null = null) {
  const onSelect = vi.fn();
  const onPageChange = vi.fn();
  render(
    <PageViewer
      analysisId="a1"
      pages={result.pages}
      findings={findings}
      currentPage={currentPage}
      onPageChange={onPageChange}
      selectedId={selectedId}
      onSelect={onSelect}
    />,
  );
  return { onSelect, onPageChange, user: userEvent.setup() };
}

describe("PageViewer", () => {
  it("renders the page image from the files endpoint", () => {
    setup();
    expect(screen.getByAltText("Page 1")).toHaveAttribute("src", "/api/analyses/a1/files/pages/1.jpg");
  });

  it("positions boxes from normalized coordinates and only shows boxes for the current page", () => {
    setup();
    const box = screen.getByTestId("box-f1");
    expect(box.style.left).toBe("10%");
    expect(box.style.top).toBe("20%");
    expect(box.style.width).toBe("30%");
    expect(box.style.height).toBe("5%");
    expect(box).toHaveTextContent("1");
    expect(screen.queryByTestId("box-f3")).toBeNull();
    expect(screen.queryByTestId("box-f2")).toBeNull();
  });

  it("fires onSelect when a box is clicked", async () => {
    const { onSelect, user } = setup();
    await user.click(screen.getByRole("button", { name: "Finding 1: Font mismatch in net pay" }));
    expect(onSelect).toHaveBeenCalledWith("f1");
  });

  it("shows boxes for another page and marks selection", () => {
    setup(2, "f3");
    const box = screen.getByTestId("box-f3");
    expect(box.style.left).toBe("50%");
    expect(box).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByTestId("box-f1")).toBeNull();
  });

  it("switches pages via the selector", async () => {
    const { onPageChange, user } = setup();
    await user.selectOptions(screen.getByLabelText("Page"), "2");
    expect(onPageChange).toHaveBeenCalledWith(2);
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPageChange).toHaveBeenLastCalledWith(2);
  });

  it("toggles overlay layers with an opacity slider", async () => {
    const { user } = setup();
    expect(screen.queryByLabelText(/opacity/i)).toBeNull();
    await user.click(screen.getByRole("radio", { name: "ELA" }));
    expect(screen.getByAltText("ELA layer for page 1")).toHaveAttribute("src", "/api/analyses/a1/files/layers/1_ela.png");
    expect(screen.getByLabelText("ELA opacity")).toBeInTheDocument();
  });

  it("hides the layer toggle when a page has no layers", () => {
    setup(2);
    expect(screen.queryByRole("radiogroup", { name: "Layer" })).toBeNull();
  });

  it("changes zoom", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("radio", { name: "200%" }));
    expect(screen.getByTestId("page-canvas").style.width).toBe("2000px");
    await user.click(screen.getByRole("radio", { name: "Fit" }));
    expect(screen.getByTestId("page-canvas").style.width).toBe("100%");
  });
});
