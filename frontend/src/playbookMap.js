// Maps every detection rule ID to its own response playbook. The files are
// served from frontend/public/playbooks/, which is copied from the repository's
// playbooks/ directory by scripts/sync-playbooks.mjs at dev/build time (one
// authored copy). Any rule without an entry falls back to the umbrella playbook.
export const PLAYBOOK_FALLBACK = "incident-response.md";

export const PLAYBOOK_MAP = {
  "WEB-SQLI-001": "web-sqli.md",
  "WEB-XSS-001": "web-xss.md",
  "WEB-CMD-001": "web-command-injection.md",
  "WEB-LFI-001": "web-traversal-lfi.md",
  "WEB-SCAN-001": "web-scanner-user-agent.md",
  "WEB-BF-001": "web-login-bruteforce.md",
  "WEB-FLOOD-001": "http-flood.md",
  "SSH-BF-001": "ssh-brute-force.md",
  "SSH-SUCCESS-001": "ssh-success-after-bruteforce.md",
  "NET-PORTSCAN-001": "port-scan.md",
  "IDS-SIG-001": "ids-signature.md",
  "DNS-ANOMALY-001": "unusual-dns.md",
  "NET-OUTBOUND-001": "unusual-outbound.md",
};

// Resolve the playbook filename for a rule, falling back to the umbrella
// playbook so an unmapped (e.g. newly added) rule still shows something useful.
export function playbookFor(ruleId) {
  return PLAYBOOK_MAP[ruleId] || PLAYBOOK_FALLBACK;
}
