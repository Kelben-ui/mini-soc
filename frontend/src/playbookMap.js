// Maps every detection rule ID to the single, canonical incident-response
// playbook. The file is served from frontend/public/playbooks/, which is copied
// from the repository's playbooks/ directory by scripts/sync-playbooks.mjs at
// dev/build time (one authored copy).
const PLAYBOOK = "incident-response.md";

export const PLAYBOOK_MAP = {
  "WEB-SQLI-001": PLAYBOOK,
  "WEB-XSS-001": PLAYBOOK,
  "WEB-CMD-001": PLAYBOOK,
  "WEB-LFI-001": PLAYBOOK,
  "WEB-SCAN-001": PLAYBOOK,
  "WEB-BF-001": PLAYBOOK,
  "WEB-FLOOD-001": PLAYBOOK,
  "SSH-BF-001": PLAYBOOK,
  "SSH-SUCCESS-001": PLAYBOOK,
  "NET-PORTSCAN-001": PLAYBOOK,
  "IDS-SIG-001": PLAYBOOK,
  "DNS-ANOMALY-001": PLAYBOOK,
  "NET-OUTBOUND-001": PLAYBOOK,
};
