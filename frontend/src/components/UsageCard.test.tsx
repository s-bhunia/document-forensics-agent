import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { UsageCard } from "./UsageCard";
import { usageFixture } from "../test/fixtures";

describe("UsageCard", () => {
  it("renders formatted cost and token values", () => {
    render(<UsageCard usage={usageFixture} />);
    expect(screen.getByTestId("usage-per-page")).toHaveTextContent("$0.0812 per page");
    expect(screen.getByTestId("usage-total")).toHaveTextContent("$0.1624");
    expect(screen.getByTestId("usage-calls")).toHaveTextContent("9");
    expect(screen.getByTestId("usage-input")).toHaveTextContent("34.2k");
    expect(screen.getByTestId("usage-output")).toHaveTextContent("5.5k");
  });

  it("shows cached and thinking breakdowns", () => {
    render(<UsageCard usage={usageFixture} />);
    expect(screen.getByText("of which 12k cached")).toBeInTheDocument();
    expect(screen.getByText("incl. 3.1k thinking")).toBeInTheDocument();
  });

  it("omits breakdowns that are zero", () => {
    render(<UsageCard usage={{ ...usageFixture, cached_tokens: 0, thinking_tokens: 0 }} />);
    expect(screen.queryByText(/of which .* cached/)).toBeNull();
    expect(screen.queryByText(/incl. .* thinking/)).toBeNull();
  });

  it("lists the prices used per 1M tokens", () => {
    render(<UsageCard usage={usageFixture} />);
    expect(screen.getByTestId("usage-prices")).toHaveTextContent(
      "Prices per 1M tokens: input $3.00 · cached input $0.30 · output $15.00",
    );
  });
});
