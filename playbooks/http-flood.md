# HTTP flood (`WEB-FLOOD-001`)

**Severity** MEDIUM · **Category** web · **MITRE** T1498 · **Source** Nginx access log

> A high rate of HTTP requests from one source in a short window. Check whether
> the host is saturated and whether it is one client or many.

## Trigger

≥301 requests with HTTP status `301` from one `src_ip` within 60 s. Threshold
lives in `rules/http_flood.yaml`.

> There is deliberately **no** attack-sim script for this: a burst of this volume
> from a laptop at an internet-facing instance resembles the DoS traffic AWS
> restricts. It is covered by the detection replay suite and the synthetic nginx
> log in `sample-data/`.

## Triage

1. Confirm the request rate and status code; check whether the host is
   CPU/connection saturated (`top`, `ss -s`).
2. Correlate for a preceding scan — a flood is often automated abuse of a
   discovered redirect endpoint.
3. Distinguish a single misbehaving client from a distributed flood (many source
   IPs → blocking one will not help).

## Evidence

- Export the flood events; record `src_ip`, requests/second, and duration.

## Containment

- Single source → **Block IP** (1800–3600 s).
- Distributed sources → blocking individual IPs is ineffective; note it and treat
  the Security Group / upstream mitigation as the real control.

## Recovery / Closure

- Confirm the host recovers once traffic stops.
- Document rate and duration, then close as **RESOLVED**.

## Related

- **Rule definition:** `rules/http_flood.yaml`
- **Reproduce:** replay only — `detection/tests/replay_test.py` + `sample-data/`
- **Platform model, universal steps, containment and closure:** [`incident-response.md`](/playbooks/incident-response.md)
