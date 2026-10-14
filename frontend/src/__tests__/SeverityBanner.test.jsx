import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import SeverityBanner from "../components/SeverityBanner";

describe("SeverityBanner", () => {
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
});
