import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const getAlerts = vi.fn();

vi.mock("../api/alerts", () => ({ getAlerts: (...args) => getAlerts(...args) }));

import AlertsList from "../pages/AlertsList";

describe("AlertsList", () => {
  beforeEach(() => {
    getAlerts.mockReset();
    getAlerts.mockResolvedValue({ data: { items: [], total: 0 } });
  });

  it("polls without filters on load", async () => {
    render(
      <MemoryRouter>
        <AlertsList />
      </MemoryRouter>
    );

    await waitFor(() => expect(getAlerts).toHaveBeenCalled());
    expect(getAlerts.mock.calls[0][0].start_time).toBeUndefined();
    expect(getAlerts.mock.calls[0][0].end_time).toBeUndefined();
  });

  it("sends start_time and end_time when a time range is set", async () => {
    render(
      <MemoryRouter>
        <AlertsList />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/from/i), {
      target: { value: "2026-10-14T10:00" },
    });

    await waitFor(() =>
      expect(getAlerts).toHaveBeenCalledWith(
        expect.objectContaining({
          start_time: new Date("2026-10-14T10:00").toISOString(),
        })
      )
    );

    fireEvent.change(screen.getByLabelText(/to/i), {
      target: { value: "2026-10-14T11:00" },
    });

    await waitFor(() =>
      expect(getAlerts).toHaveBeenCalledWith(
        expect.objectContaining({
          end_time: new Date("2026-10-14T11:00").toISOString(),
        })
      )
    );
  });

  it("links each alert row to its rule's playbook", async () => {
    getAlerts.mockResolvedValue({
      data: {
        items: [
          {
            alert_id: 7,
            title: "SSH brute force",
            severity: "HIGH",
            status: "NEW",
            src_ip: "198.51.100.10",
            last_seen: "2026-10-18T12:00:00Z",
            rule_id: "SSH-BF-001",
          },
          {
            alert_id: 8,
            title: "Unknown rule",
            severity: "LOW",
            status: "NEW",
            src_ip: "198.51.100.11",
            last_seen: "2026-10-18T12:05:00Z",
            rule_id: "NEW-RULE-999",
          },
        ],
        total: 2,
      },
    });

    render(
      <MemoryRouter>
        <AlertsList />
      </MemoryRouter>
    );

    // Known rule resolves to its own playbook file...
    const mapped = await screen.findByTitle(
      "Response playbook for SSH-BF-001"
    );
    expect(mapped).toHaveAttribute("href", "/playbooks/ssh-brute-force.md");

    // ...and an unmapped rule falls back to the umbrella playbook.
    const fallback = screen.getByTitle("Response playbook for NEW-RULE-999");
    expect(fallback).toHaveAttribute(
      "href",
      "/playbooks/incident-response.md"
    );
  });
});
