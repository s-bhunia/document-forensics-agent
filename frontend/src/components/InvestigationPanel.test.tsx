import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InvestigationPanel } from "./InvestigationPanel";
import type { InvestigationSuccess } from "../api/types";
import { completedFixture, usageFixture } from "../test/fixtures";

const investigation = completedFixture.result!.investigation as InvestigationSuccess;

describe("InvestigationPanel", () => {
  it("renders model, verdict and an ordered timeline of steps", () => {
    render(<InvestigationPanel investigation={investigation} />);
    expect(screen.getByText("claude-vision-test")).toBeInTheDocument();
    expect(screen.getByText("Suspicious")).toBeInTheDocument();

    const steps = within(screen.getByRole("list", { name: "Investigation steps" })).getAllByRole("listitem");
    expect(steps).toHaveLength(4);
    expect(steps[0]).toHaveTextContent("Viewed page");
    expect(steps[0]).toHaveTextContent("page=1");
    expect(steps[1]).toHaveTextContent("Zoomed into region");
    expect(steps[2]).toHaveTextContent("Compared with peers");
    expect(steps[3]).toHaveTextContent("Submitted report");
  });

  it("marks failed steps", () => {
    render(<InvestigationPanel investigation={investigation} />);
    const steps = screen.getAllByTestId("investigation-step");
    expect(steps[2]).toHaveAttribute("data-ok", "false");
    expect(within(steps[2]).getByText("Failed")).toBeInTheDocument();
    expect(within(steps[0]).queryByText("Failed")).toBeNull();
    expect(screen.getByText(/1 failed/)).toBeInTheDocument();
  });

  it("humanizes unknown tool names", () => {
    render(
      <InvestigationPanel
        investigation={{ ...investigation, steps: [{ tool: "check_fonts", input: "", ok: true }] }}
      />,
    );
    expect(screen.getByText("Check fonts")).toBeInTheDocument();
  });

  it("shows the failure notice for an errored investigation", () => {
    render(<InvestigationPanel investigation={{ error: "Rate limited", usage: null }} />);
    expect(screen.getByText("AI investigation failed — showing rule-based result")).toBeInTheDocument();
    expect(screen.getByText("Rate limited")).toBeInTheDocument();
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.queryByText("Cost & tokens")).toBeNull();
  });

  it("shows the cost card in the header when usage exists", () => {
    render(<InvestigationPanel investigation={investigation} />);
    expect(screen.getByText("Cost & tokens")).toBeInTheDocument();
    expect(screen.getByTestId("usage-per-page")).toHaveTextContent("$0.0812 per page");
  });

  it("hides the cost card when usage is null", () => {
    render(<InvestigationPanel investigation={{ ...investigation, usage: null }} />);
    expect(screen.queryByText("Cost & tokens")).toBeNull();
  });

  it("still shows usage when the investigation failed after spending tokens", () => {
    render(<InvestigationPanel investigation={{ error: "Model timed out", usage: usageFixture }} />);
    expect(screen.getByText("AI investigation failed — showing rule-based result")).toBeInTheDocument();
    expect(screen.getByTestId("usage-total")).toHaveTextContent("$0.1624");
  });
});
