import { describe, expect, it } from "vitest";
import {
  TACTIC_ORDER,
  groupAlertsByTactic,
  tacticForTechnique,
} from "../constants/mitre";

describe("tacticForTechnique", () => {
  it("maps known techniques to their tactic", () => {
    expect(tacticForTechnique("T1110")).toBe("Credential Access");
    expect(tacticForTechnique("T1190")).toBe("Initial Access");
    expect(tacticForTechnique("t1498")).toBe("Impact");
  });

  it("resolves sub-techniques via their parent", () => {
    expect(tacticForTechnique("T1071.004")).toBe("Command and Control");
  });

  it("falls back to Other for unknown or missing techniques", () => {
    expect(tacticForTechnique("T9999")).toBe("Other");
    expect(tacticForTechnique(null)).toBe("Other");
    expect(tacticForTechnique("")).toBe("Other");
  });
});

describe("groupAlertsByTactic", () => {
  it("orders groups by kill-chain phase and alerts by time", () => {
    const alerts = [
      { alert_id: 1, mitre: "T1041", first_seen: "2026-10-14T10:05:00Z" },
      { alert_id: 2, mitre: "T1595", first_seen: "2026-10-14T10:01:00Z" },
      { alert_id: 3, mitre: "T1595", first_seen: "2026-10-14T10:03:00Z" },
      { alert_id: 4, mitre: "T9999", first_seen: "2026-10-14T10:02:00Z" },
    ];

    const groups = groupAlertsByTactic(alerts);

    expect(groups.map((group) => group.tactic)).toEqual([
      "Reconnaissance",
      "Exfiltration",
      "Other",
    ]);

    const recon = groups[0];
    expect(recon.alerts.map((alert) => alert.alert_id)).toEqual([2, 3]);
  });

  it("keeps every tactic after the known ones in the canonical order", () => {
    expect(TACTIC_ORDER[TACTIC_ORDER.length - 1]).toBe("Other");
  });
});
