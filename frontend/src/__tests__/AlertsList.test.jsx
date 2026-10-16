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
});
