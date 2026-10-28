# sample-data

Lab log samples used to verify the collector parsers and the pipeline end to
end (task 1.6). The lab host (`ip-172-31-13-199`) is currently unreachable, so
these lines are **hand-built to be byte-format-identical** to the real
sources listed below. When the box is recovered, replace them with captured
lines from the host (they must parse with `collector/parsers/*` and trigger
the rules listed in the matrix).

Regenerate: `python sample-data/generate.py`

| file | source format | rules it exercises |
|---|---|---|
| `nginx_access.log` | `deploy/nginx/mini-soc.conf` `soc` log format (§2.5) | WEB-SQLI-001, WEB-XSS-001, WEB-CMD-001, WEB-LFI-001, WEB-SCAN-001, WEB-BF-001, WEB-FLOOD-001 |
| `auth.log` | rsyslog `auth.log` (syslog prefix) | SSH-BF-001, SSH-SUCCESS-001 |
| `mini_soc_ids.json` | `ids/live_ids_ips.py` output (one JSON object per line) | NET-PORTSCAN-001, IDS-SIG-001, DNS-ANOMALY-001, NET-OUTBOUND-001 |
| `firewall_kern.log` | `kern.log` nftables log lines (`SOC_DROP:`/`SOC_ACCEPT:`/`SOC_OUT:`) | (firewall parser feed) |
| `nginx_error.log` | `/var/log/nginx/error.log` | (nginx_error parser feed) |

## Threshold rules

The files include the full volumes the threshold rules need (see
`rules/*.yaml`):

- WEB-BF-001: 20× `POST /dvwa/login.php` `401` from one src (threshold 20 / 120 s)
- WEB-FLOOD-001: 301× status-`301` GET from one src (threshold 301 / 60 s)
- SSH-BF-001: 12× `Failed password` from one src (threshold 10 / 300 s)
- SSH-SUCCESS-001: one `Accepted` line right after the burst

## Quick verification

Parse every sample line with the collector parsers (all lines must produce a
normalized event — none may return `None`):

```
python -m pytest collector/tests
```

For an end-to-end check the generated nginx/auth/ids lines can be replayed
through detection against a `DATABASE_URL`-backed SQLite database (see
`detection/tests/replay_test.py` for the wiring and `README.md` for how the
replay is run).