import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AI_NOTICE_DELAY_MS, ProcessingState } from "./ProcessingState";

describe("ProcessingState", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("switches to the AI examiner message after prolonged processing", () => {
    render(<ProcessingState status="processing" filename="scan.pdf" />);
    expect(screen.getByRole("heading", { name: "Analyzing document" })).toBeInTheDocument();
    expect(screen.queryByText(/this can take a few minutes/)).toBeNull();

    act(() => {
      vi.advanceTimersByTime(AI_NOTICE_DELAY_MS);
    });
    expect(screen.getByRole("heading", { name: "AI examiner is investigating…" })).toBeInTheDocument();
    expect(screen.getByText("AI examiner is investigating… this can take a few minutes.")).toBeInTheDocument();
  });

  it("does not show the AI message while queued", () => {
    render(<ProcessingState status="queued" filename="scan.pdf" />);
    act(() => {
      vi.advanceTimersByTime(AI_NOTICE_DELAY_MS * 2);
    });
    expect(screen.getByRole("heading", { name: "Waiting in queue" })).toBeInTheDocument();
    expect(screen.queryByText(/this can take a few minutes/)).toBeNull();
  });
});
