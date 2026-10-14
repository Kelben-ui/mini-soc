import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const getChains = vi.fn();
const promoteChain = vi.fn();

vi.mock("../api/chains", () => ({
  getChains: (...args) => getChains(...args),
  promoteChain: (...args) => promoteChain(...args),
}));

import ChainsList from "../pages/ChainsList";

const CHAIN = {
  chain_id: 9001,
  alert_count: 2,
  max_severity: "CRITICAL",
  categories: ["authentication", "web"],
  src_ips: ["203.0.113.5"],
  affected_hosts: ["web-1"],
  first_seen: "2026-10-14T10:00:00Z",
  last_seen: "2026-10-14T10:30:00Z",
  incident_id: null,
  promoted: false,
};

describe("ChainsList", () => {
  beforeEach(() => {
    getChains.mockReset();
    promoteChain.mockReset();
    getChains.mockResolvedValue({ data: { items: [CHAIN], total: 1 } });
  });

  it("lists correlated chains", async () => {
    render(
      <MemoryRouter>
        <ChainsList />
      </MemoryRouter>
    );

    expect(await screen.findByText("Chain 9001")).toBeInTheDocument();
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
  });

  it("promotes a chain after confirmation", async () => {
    promoteChain.mockResolvedValue({
      data: { incident_id: 42, incident_code: "INC-0042" },
    });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <MemoryRouter>
        <ChainsList />
      </MemoryRouter>
    );

    const button = await screen.findByRole("button", { name: /promote/i });
    await userEvent.click(button);

    await waitFor(() => expect(promoteChain).toHaveBeenCalledWith(9001));
    expect(confirmSpy).toHaveBeenCalled();
    expect(await screen.findByText(/INC-0042/)).toBeInTheDocument();

    confirmSpy.mockRestore();
  });
});
