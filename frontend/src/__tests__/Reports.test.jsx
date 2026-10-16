import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const getStats = vi.fn();
const getIncidents = vi.fn();
const openIncidentReport = vi.fn();
const downloadIncidentReport = vi.fn();

vi.mock("../api/stats", () => ({ getStats: (...args) => getStats(...args) }));
vi.mock("../api/incidents", () => ({
  getIncidents: (...args) => getIncidents(...args),
  openIncidentReport: (...args) => openIncidentReport(...args),
  downloadIncidentReport: (...args) => downloadIncidentReport(...args),
}));

import Reports from "../pages/Reports";

const INCIDENT = {
  incident_id: 7,
  incident_code: "INC-0007",
  title: "SSH brute force",
  severity: "HIGH",
  status: "open",
  created_at: "2026-10-14T10:00:00Z",
};

describe("Reports", () => {
  beforeEach(() => {
    getStats.mockReset();
    getIncidents.mockReset();
    openIncidentReport.mockReset();
    downloadIncidentReport.mockReset();
    getStats.mockResolvedValue({
      data: {
        total_alerts: 1,
        total_incidents: 1,
        open_incidents: 1,
        threat_level: "LOW",
        alerts_by_severity: { HIGH: 1 },
      },
    });
    getIncidents.mockResolvedValue({ data: [INCIDENT] });
  });

  it("lists incidents with view and download actions", async () => {
    render(
      <MemoryRouter>
        <Reports />
      </MemoryRouter>
    );

    expect(await screen.findByText("INC-0007")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view report/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^download$/i })).toBeInTheDocument();
  });

  it("downloads the report for an incident", async () => {
    render(
      <MemoryRouter>
        <Reports />
      </MemoryRouter>
    );

    await userEvent.click(await screen.findByRole("button", { name: /^download$/i }));

    expect(downloadIncidentReport).toHaveBeenCalledWith(7, "INC-0007");
  });
});
