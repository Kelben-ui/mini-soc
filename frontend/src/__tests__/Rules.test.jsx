import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api/rules", () => ({
  getRules: vi.fn(() =>
    Promise.resolve({
      data: [
        {
          id: "SSH-BF-001",
          name: "SSH brute force",
          severity: "HIGH",
          category: "authentication",
          mitre: "T1110",
          enabled: true,
          alerts_count: 5,
          last_fired: "2026-10-14T10:00:00Z",
        },
      ],
    })
  ),
}));

import Rules from "../pages/Rules";

describe("Rules page", () => {
  it("shows the technique, tactic and live fire count for each rule", async () => {
    render(<Rules />);

    expect(await screen.findByText("SSH brute force")).toBeInTheDocument();
    expect(screen.getByText("T1110")).toBeInTheDocument();
    expect(screen.getByText("Credential Access")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("enabled")).toBeInTheDocument();
  });
});
