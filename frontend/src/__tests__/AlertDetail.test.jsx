import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const getAlert = vi.fn();
const recordAction = vi.fn();

vi.mock("../api/alerts", () => ({
  getAlert: (...args) => getAlert(...args),
  updateAlert: vi.fn(),
  promoteAlert: vi.fn(),
  exportAlertEvidence: vi.fn(),
}));

vi.mock("../api/incidents", () => ({
  recordAction: (...args) => recordAction(...args),
}));

vi.mock("../api/client", () => ({ default: { get: vi.fn() } }));

import client from "../api/client";
import AlertDetail from "../pages/AlertDetail";

const ALERT = {
  alert_id: 7,
  rule_id: "SSH-BF-001",
  title: "SSH brute force",
  severity: "HIGH",
  status: "NEW",
  category: "authentication",
  mitre: "T1110",
  src_ip: "203.0.113.9",
  dst_ip: "10.0.0.5",
  dst_host: "soc-01",
  incident_id: 3,
  count: 12,
  events: [],
};

function renderAlert() {
  return render(
    <MemoryRouter initialEntries={["/alerts/7"]}>
      <Routes>
        <Route path="/alerts/:id" element={<AlertDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AlertDetail playbook", () => {
  beforeEach(() => {
    getAlert.mockReset();
    recordAction.mockReset();
    client.get.mockReset();

    getAlert.mockResolvedValue({ data: { ...ALERT } });
    client.get.mockResolvedValue({ data: [] });

    localStorage.setItem("role", "lead");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("# SSH brute force\n\n## Trigger\n\nA burst.\n"),
    });
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders the rule's playbook and the action bar", async () => {
    renderAlert();

    // Fetches the playbook for the alert's rule.
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/playbooks/ssh-brute-force.md")
    );

    // The markdown body is rendered (not shown as raw text). "Trigger" is a
    // heading that only comes from the playbook.
    expect(
      await screen.findByRole("heading", { name: "Trigger" })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: /open incident #3/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /block source ip/i })).toBeEnabled();
    expect(
      screen.getByRole("link", { name: /open raw \/ print/i })
    ).toHaveAttribute("href", "/playbooks/ssh-brute-force.md");
  });

  it("records a pending block IP action for the source on demand", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    recordAction.mockResolvedValue({ data: { id: 11 } });

    renderAlert();

    await screen.findByRole("heading", { name: "Trigger" });
    await userEvent.click(
      screen.getByRole("button", { name: /block source ip/i })
    );

    await waitFor(() => expect(recordAction).toHaveBeenCalled());
    expect(recordAction).toHaveBeenCalledWith(
      3,
      expect.objectContaining({
        action_type: "block ip",
        target: "203.0.113.9",
      })
    );
  });
});
