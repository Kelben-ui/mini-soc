// ATT&CK tactic ordering used by the kill-chain timeline (task 7.7).
export const TACTIC_ORDER = [
  "Reconnaissance",
  "Initial Access",
  "Execution",
  "Persistence",
  "Privilege Escalation",
  "Defense Evasion",
  "Credential Access",
  "Discovery",
  "Lateral Movement",
  "Collection",
  "Command and Control",
  "Exfiltration",
  "Impact",
  "Other",
];

// Technique -> tactic, covering every rule shipped in rules/.
const TECHNIQUE_TACTICS = {
  T1595: "Reconnaissance",
  T1190: "Initial Access",
  T1059: "Execution",
  T1078: "Defense Evasion",
  T1110: "Credential Access",
  T1046: "Discovery",
  T1083: "Discovery",
  T1071: "Command and Control",
  "T1071.004": "Command and Control",
  T1041: "Exfiltration",
  T1498: "Impact",
};

export function tacticForTechnique(mitre) {
  if (!mitre) return "Other";

  const key = String(mitre).trim().toUpperCase();
  if (TECHNIQUE_TACTICS[key]) return TECHNIQUE_TACTICS[key];

  const base = key.split(".")[0];
  return TECHNIQUE_TACTICS[base] || "Other";
}

export function tacticRank(tactic) {
  const index = TACTIC_ORDER.indexOf(tactic);
  return index === -1 ? TACTIC_ORDER.length : index;
}

// Group alerts into {tactic, alerts[]} in kill-chain order, oldest first.
export function groupAlertsByTactic(alerts) {
  const groups = new Map();

  [...alerts]
    .sort(
      (a, b) =>
        new Date(a.first_seen ?? 0).getTime() - new Date(b.first_seen ?? 0).getTime()
    )
    .forEach((alert) => {
      const tactic = tacticForTechnique(alert.mitre);
      if (!groups.has(tactic)) groups.set(tactic, []);
      groups.get(tactic).push(alert);
    });

  return [...groups.entries()]
    .sort((a, b) => TACTIC_ORDER.indexOf(a[0]) - TACTIC_ORDER.indexOf(b[0]))
    .map(([tactic, items]) => ({ tactic, alerts: items }));
}
