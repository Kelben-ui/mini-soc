import { describe, expect, it } from "vitest";
import { formatBytes, formatDateTime, formatDuration } from "../utils/format";

describe("formatDuration", () => {
  it("renders sub-minute durations in seconds", () => {
    expect(formatDuration(45)).toBe("45s");
  });

  it("renders minutes and seconds", () => {
    expect(formatDuration(125)).toBe("2m 5s");
  });

  it("renders whole minutes without a trailing zero", () => {
    expect(formatDuration(120)).toBe("2m");
  });

  it("renders hours and minutes", () => {
    expect(formatDuration(3720)).toBe("1h 2m");
  });

  it("uses an em dash for missing values", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
  });
});

describe("formatBytes", () => {
  it("renders bytes and kilobytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
  });
});

describe("formatDateTime", () => {
  it("returns an em dash for empty values", () => {
    expect(formatDateTime(null)).toBe("—");
  });
});
