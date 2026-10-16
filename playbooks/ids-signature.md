# IDS signature detection (`IDS-SIG-001`)

**Severity** HIGH (mapped) · **Category** ids · **MITRE** T1059 · **Source** custom IDS (`ids/live_ids_ips.py`)

> A generic alert from the custom IDS that the collector could not map to a more
> specific rule. Read the signature to work out which scenario this really is.

## Trigger

An IDS alert whose kind is not mapped to a dedicated rule — for example the SSH
brute-force signature (`9000002`) or a SYN flood (`9000003`). The catch-all lives
in `rules/ids_signature.yaml`; severity is taken from the signature's
`severity`/`priority`.

| Signature id | Really means | Follow |
|---|---|---|
| `9000001` | port scan | `port-scan.md` |
| `9000002` | SSH brute force | `ssh-brute-force.md` |
| `9000003` | SYN flood | treat like `http-flood.md` |
| `9000004` | DNS anomaly | `unusual-dns.md` |
| `9000005` | unusual outbound | `unusual-outbound.md` |

## Triage

1. Read the signature `msg`/`category` on the linked event to identify which
   signature fired.
2. Most often this is **duplicate telemetry** for an activity that already has its
   own alert (e.g. `9000002` alongside `SSH-BF-001`). Investigate it together with
   that alert instead of counting it twice.
3. For a SYN-flood-shaped `IDS-SIG-001`, follow the HTTP flood playbook.

## Evidence

- Export the linked IDS events; record the signature id/msg and the source.

## Containment

- Follow the mapped scenario's containment decision.
- Only `block IP` is executable; it is recorded then confirmed by a human.

## Recovery / Closure

- Close as **RESOLVED**, or **FALSE POSITIVE** for approved test traffic.
- When it duplicates another alert, close it as part of that alert's incident.

## Related

- **Rule definition:** `rules/ids_signature.yaml`
- **Reproduce:** `attack-sim/port-scan.sh <target>` or
  `attack-sim/ssh-brute-force.sh <target> testuser passlist.txt` (both feed the IDS)
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
