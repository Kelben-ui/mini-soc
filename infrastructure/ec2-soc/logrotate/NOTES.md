# Log rotation notes (task 8.1)

There is no single "mini-soc" log file: the services log to **journald**, so
rotation is handled by `journald.conf` (`SystemMaxUse`), not `logrotate`.
Only the IDS output is a plain file, plus the two nginx logs.

## What is a file

| Path | Written by | Rotation |
|---|---|---|
| `/var/log/nginx/access.log` | nginx (package) | nginx package logrotate (daily, 14, compress) |
| `/var/log/nginx/error.log` | nginx (package) | nginx package logrotate |
| `/var/log/mini_soc_ids.json` | `ids/live_ids_ips.py` | this file (below) |

Everything else (`soc-backend`, `soc-collector`, `soc-detection`,
`soc-agent`, `mini-soc-ids`) goes to the journal and is bounded by
`/etc/systemd/journald.conf` rather than by logrotate.

## `/etc/logrotate.d/mini-soc-ids`

```
/var/log/mini_soc_ids.json {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 mini-soc-ids mini-soc
    sharedscripts
    postrotate
        systemctl kill -s HUP mini-soc-ids.service >/dev/null 2>&1 || true
    endscript
}
```

`live_ids_ips.py` reopens `IDS_OUTPUT` on `SIGHUP`, so the `postrotate`
hook is what makes the new file get written without restarting the daemon.
If that signal handling is ever removed, drop the `postrotate` block and
rotate on writer restart instead.
