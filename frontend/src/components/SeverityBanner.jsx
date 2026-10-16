import { useEffect, useState } from "react";
import { getStats } from "../api/stats";
import { getAlerts } from "../api/alerts";
import { isLoggedIn } from "../api/auth";
import { threatLevelClasses } from "../utils/severity";

const POLL_MS = 10000;

const URGENT_LEVELS = new Set(["HIGH", "CRITICAL"]);

// Alert statuses that no longer count as an active/urgent alert.
const INACTIVE_STATUSES = new Set([
  "RESOLVED",
  "FALSE POSITIVE",
  "CLOSED",
  "FALSE_POSITIVE",
]);

// Newest not-yet-closed alert at CRITICAL (else HIGH), so the banner can name
// the specific attack (spec: "HIGH SEVERITY — SSH BRUTE FORCE").
async function fetchNewestUrgentAlert() {
  for (const severity of ["CRITICAL", "HIGH"]) {
    try {
      const res = await getAlerts({ severity, limit: 5 });
      const items = Array.isArray(res.data?.items) ? res.data.items : [];

      const active = items.find(
        (item) => !INACTIVE_STATUSES.has((item.status || "").toUpperCase())
      );

      if (active) return active;
    } catch {
      // Ignore and try the next severity; the posture line still renders.
    }
  }

  return null;
}

/**
 * Overall posture bar (task 7.10).
 *
 * The threat level is computed server-side in ``GET /api/stats`` from open
 * alerts and open incidents, so every client agrees on the current posture.
 * When the level is HIGH or CRITICAL the banner also names the newest active
 * alert (rule title) so a new high-severity detection is unmistakable.
 *
 * Pass a ``stats`` prop to render a fixed snapshot (tests); otherwise the
 * banner polls the API itself.
 */
export default function SeverityBanner({ stats: injected }) {
  const [stats, setStats] = useState(injected || null);
  const [alert, setAlert] = useState(null);

  useEffect(() => {
    if (injected) {
      setStats(injected);
      return undefined;
    }

    if (!isLoggedIn()) return undefined;

    let cancelled = false;

    function refresh() {
      getStats()
        .then((res) => {
          if (cancelled) return;

          setStats(res.data);

          const level = (res.data?.threat_level || "LOW").toUpperCase();

          if (URGENT_LEVELS.has(level)) {
            fetchNewestUrgentAlert().then((found) => {
              if (!cancelled) setAlert(found);
            });
          } else {
            setAlert(null);
          }
        })
        .catch(() => {});
    }

    refresh();
    const interval = setInterval(refresh, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [injected]);

  if (!stats) return null;

  const level = (stats.threat_level || "LOW").toUpperCase();
  const active = stats.active_alerts ?? 0;
  const openIncidents = stats.open_incidents ?? 0;
  const urgent = URGENT_LEVELS.has(level);

  const headline =
    urgent && alert
      ? `${level} SEVERITY — ${(alert.title || alert.rule_id || "ALERT").toUpperCase()}`
      : `${level} threat level`;

  return (
    <div
      role="status"
      className={`flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-4 py-2 text-sm ${threatLevelClasses(
        level
      )}`}
    >
      <span className="font-bold uppercase tracking-wide">{headline}</span>
      <span className="text-xs opacity-90">
        {active} active alert{active === 1 ? "" : "s"} · {openIncidents} open
        incident{openIncidents === 1 ? "" : "s"}
      </span>
      {urgent && (
        <a
          href={alert ? `/alerts/${alert.alert_id}` : "/alerts"}
          className="ml-auto rounded bg-black/30 px-2 py-0.5 text-xs font-semibold hover:bg-black/50"
        >
          Investigate
        </a>
      )}
    </div>
  );
}
