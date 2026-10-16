import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const getStats = vi.fn();
const getAlerts = vi.fn();
const isLoggedIn = vi.fn();

vi.mock("../api/stats", () => ({ getStats: (...args) => getStats(...args) }));
vi.mock("../api/alerts", () => ({ getAlerts: (...args) => getAlerts(...args) }));
vi.mock("../api/auth", () => ({ isLoggedIn: (...args) => isLoggedIn(...args) }));

import SeverityBanner from "../components/SeverityBanner";

describe("SeverityBanner", () => {
  beforeEach(() => {
    getStats.mockReset();
    getAlerts.mockReset();
    isLoggedIn.mockReset();
  });

  it("renders the overall threat level and posture counts", () => {
    render(
      <SeverityBanner
        stats={{ threat_level: "CRITICAL", active_alerts: 3, open_incidents: 2 }}
      />
    );

    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent(/CRITICAL threat level/i);
    expect(banner).toHaveTextContent(/3 active alerts/i);
    expect(banner).toHaveTextContent(/2 open incidents/i);
    expect(screen.getByText(/investigate/i)).toBeInTheDocument();
  });

  it("omits the call to action for a low threat level", () => {
    render(
      <SeverityBanner
        stats={{ threat_level: "LOW", active_alerts: 0, open_incidents: 0 }}
      />
    );

    expect(screen.getByRole("status")).toHaveTextContent(/LOW threat level/i);
    expect(screen.queryByText(/investigate/i)).not.toBeInTheDocument();
  });

  it("renders nothing without stats", () => {
    const { container } = render(<SeverityBanner stats={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names the newest active high-severity alert", async () => {
    isLoggedIn.mockReturnValue(true);
    getStats.mockResolvedValue({
      data: { threat_level: "HIGH", active_alerts: 1, open_incidents: 0 },
    });
    getAlerts.mockResolvedValue({
      data: {
        items: [{ alert_id: 5, title: "SSH Brute Force", status: "NEW" }],
        total: 1,
      },
    });

    render(<SeverityBanner />);

    expect(await screen.findByText(/HIGH SEVERITY/i)).toBeInTheDocument();
    expect(screen.getByText(/SSH BRUTE FORCE/i)).toBeInTheDocument();
  });

  it("does not query alerts when the threat level is low", async () => {
    isLoggedIn.mockReturnValue(true);
    getStats.mockResolvedValue({
      data: { threat_level: "LOW", active_alerts: 0, open_incidents: 0 },
    });

    render(<SeverityBanner />);

    expect(await screen.findByText(/LOW threat level/i)).toBeInTheDocument();
    expect(getAlerts).not.toHaveBeenCalled();
  });
});
