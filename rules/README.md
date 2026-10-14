# Detection Rules (`rules/`)

Declarative YAML rules evaluated by the detection engine
([`../detection/`](../detection/)) against normalized events. Rules are data:
adding, tuning or disabling one never requires a code change.

## Rule files

| File | ID | Name | Severity | Fires on |
|---|---|---|---|---|
| `sqli.yaml` | WEB-SQLI-001 | SQL injection | HIGH | `' or `, `" or `, `union select`, `select `, ` from `, `sleep(`, `--`, `/*` in a web request |
| `xss.yaml` | WEB-XSS-001 | Cross-site scripting | MEDIUM | `<script`, `javascript:`, `onerror=`, `onload=` |
| `command_injection.yaml` | WEB-CMD-001 | Command injection | HIGH | `; id`, `; whoami`, `| id`, `| whoami`, `&& id`, `&& whoami` |
| `traversal_lfi.yaml` | WEB-LFI-001 | Directory traversal / LFI | HIGH | `../`, `/etc/passwd`, `php://` |
| `scanner_user_agent.yaml` | WEB-SCAN-001 | Scanner user agent | MEDIUM | sqlmap / nikto / nmap / gobuster in the User-Agent |
| `web_login_bruteforce.yaml` | WEB-BF-001 | Web login brute force | HIGH | ≥20 `POST /login` from one `src_ip` / 120 s |
| `http_flood.yaml` | WEB-FLOOD-001 | HTTP flood | MEDIUM | ≥301 requests with status `301` from one `src_ip` / 60 s |
| `ssh_brute_force.yaml` | SSH-BF-001 | SSH brute force | HIGH | ≥10 failed `ssh_login` per `src_ip`→`dst_ip` / 300 s |
| `ssh_success_after_bruteforce.yaml` | SSH-SUCCESS-001 | Login success after brute force | CRITICAL | a successful `ssh_login` correlated to an open brute-force alert |
| `port_scan.yaml` | NET-PORTSCAN-001 | Port scan | MEDIUM | IDS/nftables port-scan event (≥20 distinct ports from one source) |
| `ids_signature.yaml` | IDS-SIG-001 | Generic IDS signature | HIGH | IDS alert not mapped to a specific action (SSH-sig 9000002, SYN flood 9000003) |
| `unusual_dns.yaml` | DNS-ANOMALY-001 | Unusual DNS activity | LOW | IDS DNS signature (9000004) |
| `unusual_outbound.yaml` | NET-OUTBOUND-001 | Unusual outbound connection | MEDIUM | outbound flow to a port outside 53/80/443/123 |
| `allowlist.yaml` | — | Allow-list | — | Suppresses known-benign sources (`global.ips`, `global.cidrs`, `per_rule`). |

MITRE techniques: WEB-SQLI-001 `T1190`, WEB-XSS-001/WEB-CMD-001 `T1059`,
WEB-LFI-001 `T1083`, WEB-SCAN-001 `T1595`, WEB-BF-001/SSH-BF-001 `T1110`,
WEB-FLOOD-001 `T1498`, SSH-SUCCESS-001 `T1078`, NET-PORTSCAN-001 `T1046`,
IDS-SIG-001 `T1059`, DNS-ANOMALY-001 `T1071.004`, NET-OUTBOUND-001 `T1041`.

## Rule schema

```yaml
id: SSH-BF-001
name: SSH brute force
severity: HIGH          # HIGH | MEDIUM | LOW | CRITICAL
category: authentication
enabled: true

match:                  # all keys must equal the event (missing key = any)
  log_type: auth
  action: ssh_login
  outcome: failure

threshold:              # optional; absent = a single match fires
  count: 10
  window_seconds: 300
  group_by: [src_ip, dst_ip]

contains:               # optional; case-insensitive substring match
  - "union select"

mitre: T1110
```

- **`match`** — exact field comparisons against the normalized event. Omitted
  fields match anything.
- **`contains`** — substring (case-insensitive) against the event's searchable
  payload. Used by the web rules.
- **`threshold`** — the rule fires once `count` matches land in `window_seconds`
  for the same `group_by` key(s). Without it, one match = one alert.
- **`allowlist.yaml`** — `global.ips`/`global.cidrs` are suppressed entirely;
  `per_rule` suppresses only the named rule for those sources. The same list is
  mirrored to `/etc/mini-soc/allowlist.txt` for the block helper.

## Adding / disabling a rule

1. Drop a new `*.yaml` into `rules/` (copy an existing file as a template).
2. Set `enabled: false` to disable one; the loader ignores it.
3. Reload: `systemctl restart soc-detection` (it loads the whole directory at
   startup).

`RULES_DIR` selects the directory (defaults to this folder in the repo; the
installer points the service at `/home/ubuntu/mini-soc/rules`).

## Verification

```bash
# Replay all rules against synthetic events (must be PASSED, 13/13)
python detection/tests/replay_test.py
```

Every rule has a live or replay trigger — see
[`../docs/testing/test-plan.md`](../docs/testing/test-plan.md) for the
rule → trigger matrix. Human-readable rule documentation is in
[`../docs/rules.md`](../docs/rules.md).
