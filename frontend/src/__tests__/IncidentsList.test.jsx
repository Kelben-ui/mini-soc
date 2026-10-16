import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const get = vi.fn();
const patch = vi.fn();
const createIncident = vi.fn();
const isLead = vi.fn();

vi.mock("../api/client", () => ({
  default: { get: (...args) => get(...args), patch: (...args) => patch(...args) },
}));
vi.mock("../api/incidents", () => ({
  createIncident: (...args) => createIncident(...args),
}));
vi.mock("../api/auth", () => ({ isLead: (...args) => isLead(...args) }));

import IncidentsList from "../pages/IncidentsList";

describe("IncidentsList", () => {
  beforeEach(() => {
    get.mockReset();
    patch.mockReset();
    createIncident.mockReset();
    isLead.mockReset();
    isLead.mockReturnValue(true);
    get.mockImplementation((url) =>
      url === "/api/users"
        ? Promise.resolve({ data: [{ id: 1, username: "alice", role: "lead" }] })
        : Promise.resolve({ data: [] })
    );
  });

  it("offers a New incident control to leads", async () => {
    render(
      <MemoryRouter>
        <IncidentsList />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole("button", { name: /new incident/i })
    ).toBeInTheDocument();
  });

  it("creates an incident manually via POST /api/incidents", async () => {
    createIncident.mockResolvedValue({
      data: { incident_id: 7, incident_code: "INC-0007" },
    });

    render(
      <MemoryRouter>
        <IncidentsList />
      </MemoryRouter>
    );

    await userEvent.click(await screen.findByRole("button", { name: /new incident/i }));
    await userEvent.type(screen.getByLabelText(/title/i), "Manual incident");
    await userEvent.click(screen.getByRole("button", { name: /create incident/i }));

    await waitFor(() => expect(createIncident).toHaveBeenCalledTimes(1));

    const payload = createIncident.mock.calls[0][0];
    expect(payload.title).toBe("Manual incident");
    expect(payload.severity).toBe("HIGH");
  });
});
