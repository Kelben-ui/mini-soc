import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const get = vi.fn();

vi.mock("../api/client", () => ({
  default: { get: (...args) => get(...args) },
}));

import EventSearch from "../pages/EventSearch";

const EVENT = {
  event_id: 1,
  timestamp: "2026-10-14T10:00:00Z",
  host: "web-01",
  log_type: "auth",
  src_ip: "203.0.113.5",
  src_port: 1234,
  dst_ip: "10.0.0.5",
  dst_port: 22,
  action: "ssh_login",
  outcome: "failure",
  raw: "raw log line",
};

describe("EventSearch", () => {
  beforeEach(() => {
    get.mockReset();
    get.mockResolvedValue({
      data: { items: [EVENT], total: 1, limit: 100, offset: 0 },
    });
  });

  it("loads events on mount and shows the live refresh note", async () => {
    render(<EventSearch />);

    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(get.mock.calls[0][0]).toBe("/api/events");
    expect(await screen.findByText("web-01")).toBeInTheDocument();
    expect(screen.getByText(/refreshes every 8s/i)).toBeInTheDocument();
  });

  it("sends the src_ip filter after pressing Search", async () => {
    render(<EventSearch />);

    fireEvent.change(screen.getByPlaceholderText(/source ip/i), {
      target: { value: "203.0.113.9" },
    });

    fireEvent.click(await screen.findByRole("button", { name: /^search$/i }));

    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        "/api/events",
        expect.objectContaining({
          params: expect.objectContaining({ src_ip: "203.0.113.9" }),
        })
      )
    );
  });
});
