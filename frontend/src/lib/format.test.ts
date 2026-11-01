import { describe, expect, it } from "vitest";
import {
  formatBytes,
  formatDateTime,
  formatDuration,
  formatPercent,
  formatRelative,
  formatTokens,
  formatUsd,
  formatUsdShort,
  humanize,
} from "./format";

describe("formatBytes", () => {
  it("formats across units", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(25 * 1024 * 1024)).toBe("25 MB");
    expect(formatBytes(3.25 * 1024 ** 3, 2)).toBe("3.25 GB");
  });

  it("handles invalid input", () => {
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(-1)).toBe("—");
    expect(formatBytes(Number.NaN)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("rounds fractions to whole percents", () => {
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(0.724)).toBe("72%");
    expect(formatPercent(0.725)).toBe("73%");
    expect(formatPercent(1)).toBe("100%");
  });

  it("clamps and handles missing values", () => {
    expect(formatPercent(1.4)).toBe("100%");
    expect(formatPercent(-0.2)).toBe("0%");
    expect(formatPercent(null)).toBe("—");
  });
});

describe("dates", () => {
  it("formats ISO timestamps", () => {
    const out = formatDateTime("2026-10-30T10:00:00Z", "en-US");
    expect(out).toMatch(/Oct/);
    expect(out).toMatch(/2026/);
    expect(out).toMatch(/30/);
  });

  it("returns a dash for invalid or empty dates", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime("not a date")).toBe("—");
    expect(formatRelative(undefined)).toBe("—");
  });

  it("formats relative times", () => {
    const now = new Date("2026-10-31T12:00:00Z");
    expect(formatRelative("2026-10-31T11:59:50Z", now)).toBe("just now");
    expect(formatRelative("2026-10-31T11:55:00Z", now)).toBe("5 minutes ago");
    expect(formatRelative("2026-10-31T09:00:00Z", now)).toBe("3 hours ago");
    expect(formatRelative("2026-10-30T12:00:00Z", now)).toBe("yesterday");
  });
});

describe("usage formatting", () => {
  it("formats token counts compactly", () => {
    expect(formatTokens(950)).toBe("950");
    expect(formatTokens(34_210)).toBe("34.2k");
    expect(formatTokens(12_000)).toBe("12k");
    expect(formatTokens(1_250_000)).toBe("1.25M");
    expect(formatTokens(2_000_000)).toBe("2M");
  });

  it("formats USD with 4 decimals under $1", () => {
    expect(formatUsd(0.0812)).toBe("$0.0812");
    expect(formatUsd(0.5)).toBe("$0.5000");
    expect(formatUsd(3.456)).toBe("$3.46");
    expect(formatUsd(null)).toBe("—");
  });

  it("formats short USD for chips", () => {
    expect(formatUsdShort(0.0812)).toBe("$0.08");
    expect(formatUsdShort(0.0042)).toBe("$0.0042");
    expect(formatUsdShort(0)).toBe("$0.00");
  });
});

describe("misc", () => {
  it("formats durations", () => {
    expect(formatDuration(250)).toBe("250 ms");
    expect(formatDuration(1520)).toBe("1.5 s");
  });

  it("humanizes keys", () => {
    expect(humanize("baseline_shift_px")).toBe("Baseline shift px");
  });
});
