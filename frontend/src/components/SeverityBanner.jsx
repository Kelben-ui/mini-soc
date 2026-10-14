import { useEffect, useState } from "react";
import { getStats } from "../api/stats";
import { isLoggedIn } from "../api/auth";
import { threatLevelClasses } from "../utils/severity";

const POLL_MS = 10000;

/**
 * Overall posture bar (task 7.10).
 *
 * The threat level is computed server-side in ``GET /api/stats`` from open
 * alerts and open incidents, so every client agrees on the current posture.
 * Pass a ``stats`` prop to render a fixed snapshot (tests); otherwise the
 * banner polls the API itself.
 */
export default function SeverityBanner({ stats: injected }) {
  const [stats, setStats] = useState(injected || null);

  useEffect(() => {
    if (injected) {
      setStats(injected);
      return undefined;
    }

    if (!isLoggedIn()) return undefined;

    let cancelled = false;

    function fetchStats() {
      getStats()
        .then((res) => {
          if (!cancelled) setStats(res.data);
        })
        .catch(() => {});
    }

    fetchStats();
    const interval = setInterval(fetchStats, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [injected]);

  if (!stats) return null;

  const level = (stats.threat_level || "LOW").toUpperCase();
  const active = stats.active_alerts ?? 0;
  const openIncidents = stats.open_incidents ?? 0;
  const urgent = level === "HIGH" || level === "CRITICAL";

  return (
    <div
      role="status"
      className={`flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-4 py-2 text-sm ${threatLevelClasses(
        level
      )}`}
    >
      <span className="font-bold uppercase tracking-wide">
        {level} threat level
      </span>
      <span className="text-xs opacity-90">
        {active} active alert{active === 1 ? "" : "s"} · {openIncidents} open
        incident{openIncidents === 1 ? "" : "s"}
      </span>
      {urgent && (
        <a
          href="/alerts"
          className="ml-auto rounded bg-black/30 px-2 py-0.5 text-xs font-semibold hover:bg-black/50"
        >
          Investigate
        </a>
      )}
    </div>
  );
}
