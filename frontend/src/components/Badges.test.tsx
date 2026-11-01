import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LabelBadge, SeverityBadge, StatusBadge } from "./Badges";

describe("SeverityBadge", () => {
  it.each([
    ["high", "High", "red"],
    ["medium", "Medium", "amber"],
    ["low", "Low", "sky"],
    ["info", "Info", "slate"],
  ] as const)("renders %s with the right text and color", (severity, text, color) => {
    render(<SeverityBadge severity={severity} />);
    const el = screen.getByText(text);
    expect(el).toHaveAttribute("data-severity", severity);
    expect(el.className).toContain(`bg-${color}-`);
  });
});

describe("LabelBadge", () => {
  it.each([
    ["likely_authentic", "Likely authentic", "emerald"],
    ["suspicious", "Suspicious", "amber"],
    ["highly_risky", "Highly risky", "red"],
  ] as const)("renders %s", (label, text, color) => {
    const { container } = render(<LabelBadge label={label} />);
    expect(screen.getByText(text)).toBeInTheDocument();
    expect(container.firstElementChild!.className).toContain(`text-${color}-`);
  });

  it("shows risk percent when provided", () => {
    render(<LabelBadge label="highly_risky" riskScore={0.914} />);
    expect(screen.getByText(/91%/)).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("renders human status text", () => {
    render(<StatusBadge status="processing" />);
    expect(screen.getByText("Processing")).toBeInTheDocument();
  });
});
