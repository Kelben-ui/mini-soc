import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import client from "../api/client";

const POLL_MS = 2000;

const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

const SEVERITY_STYLES = {
  CRITICAL: "text-red-300",
  HIGH: "text-orange-300",
  MEDIUM: "text-amber-300",
  LOW: "text-sky-300",
};

function severityCounts(alertsBySeverity) {
  const counts = {};

  Object.entries(alertsBySeverity || {}).forEach(([severity, count]) => {
    counts[severity.toUpperCase()] = count;
  });

  return counts;
}

function StatTile({ label, value, accent }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div className={`mt-1 text-3xl font-extrabold ${accent || "text-slate-100"}`}>
        {value}
      </div>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;

    function fetchStats() {
      if (inFlight) return;
      inFlight = true;
      client
        .get("/api/stats", { headers: { "Cache-Control": "no-cache" } })
        .then((res) => {
          if (cancelled) return;
          setStats(res.data);
          setError("");
        })
        .catch(() => {
          if (!cancelled) {
            setError("Could not load the dashboard. Check the backend connection.");
          }
        })
        .finally(() => {
          inFlight = false;
        });
    }

    fetchStats();
    const interval = setInterval(fetchStats, POLL_MS);
    const onFocus = () => fetchStats();
    const onVisibility = () => {
      if (document.visibilityState === "visible") fetchStats();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  if (error) {
    return <p className="text-sm text-red-400">{error}</p>;
  }

  if (!stats) {
    return <p className="text-sm text-slate-400">Loading SentinelX overview...</p>;
  }

  // Prefer the server's "active" counts (open alerts only); fall back to all
  // alerts if the backend doesn't provide them.
  const counts = severityCounts(
    stats.active_alerts_by_severity || stats.alerts_by_severity
  );
  const agents = stats.agents || [];
  const online = stats.agents_online || 0;

  return (
    <div className="space-y-6 text-slate-100">
      <h1 className="text-2xl font-bold">SentinelX Overview</h1>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Total events" value={stats.total_events} accent="text-sky-300" />
        <StatTile label="Total alerts" value={stats.total_alerts} accent="text-amber-300" />
        <StatTile
          label="Open incidents"
          value={stats.open_incidents}
          accent="text-red-300"
        />
        <StatTile
          label="Agents online"
          value={`${online}/${agents.length}`}
          accent={online === agents.length ? "text-emerald-300" : "text-orange-300"}
        />
      </div>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Active alerts by severity
        </h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {SEVERITIES.map((severity) => (
            <div
              key={severity}
              className="rounded border border-slate-800 bg-slate-950 p-3"
            >
              <div className="text-xs uppercase text-slate-500">{severity}</div>
              <div className={`text-2xl font-bold ${SEVERITY_STYLES[severity]}`}>
                {counts[severity] || 0}
              </div>
            </div>
          ))}
        </div>
      </section>

      <Panel title="Alerts over the last 24 hours">
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={stats.alerts_over_24h || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="hour"
                tickFormatter={(value) =>
                  new Date(value).toLocaleTimeString([], { hour: "2-digit" })
                }
                stroke="#64748b"
                fontSize={12}
                minTickGap={24}
              />
              <YAxis allowDecimals={false} stroke="#64748b" fontSize={12} width={28} />
              <Tooltip
                labelFormatter={(value) => new Date(value).toLocaleString()}
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #1e293b",
                  borderRadius: 6,
                }}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Line
                type="monotone"
                dataKey="count"
                name="Alerts"
                stroke="#38bdf8"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Top source IPs">
          {(stats.top_source_ips || []).length === 0 ? (
            <p className="text-sm text-slate-500">No alert data yet.</p>
          ) : (
            <ul className="space-y-2">
              {stats.top_source_ips.map((entry) => (
                <li
                  key={entry.src_ip}
                  className="flex items-center justify-between rounded bg-slate-950 px-3 py-2 text-sm"
                >
                  <span className="font-mono">{entry.src_ip}</span>
                  <span className="font-semibold text-slate-300">{entry.count}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Top attack types">
          {(stats.top_attack_types || []).length === 0 ? (
            <p className="text-sm text-slate-500">No alert data yet.</p>
          ) : (
            <ul className="space-y-2">
              {stats.top_attack_types.map((entry) => (
                <li
                  key={entry.type}
                  className="flex items-center justify-between rounded bg-slate-950 px-3 py-2 text-sm"
                >
                  <span className="capitalize">{entry.type}</span>
                  <span className="font-semibold text-slate-300">{entry.count}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Agent & IDS status">
        <div className="mb-3 flex flex-wrap gap-3">
          <span
            className={`rounded px-3 py-1 text-sm font-semibold ${
              stats.ids_status === "active"
                ? "bg-emerald-950 text-emerald-300"
                : "bg-red-950 text-red-300"
            }`}
          >
            IDS: {stats.ids_status || "unknown"}
          </span>
          <span className="rounded bg-slate-950 px-3 py-1 text-sm font-semibold text-slate-300">
            Agents online: {online}/{agents.length}
          </span>
        </div>

        {agents.length === 0 ? (
          <p className="text-sm text-slate-500">No agent heartbeats received.</p>
        ) : (
          <ul className="space-y-2">
            {agents.map((agent) => (
              <li
                key={agent.name}
                className="flex flex-wrap items-center justify-between gap-2 rounded bg-slate-950 px-3 py-2 text-sm"
              >
                <span>
                  <span
                    className={
                      agent.status === "online" ? "text-emerald-400" : "text-red-400"
                    }
                  >
                    ●
                  </span>{" "}
                  {agent.name}
                  {agent.host ? ` · ${agent.host}` : ""}
                </span>
                <span className="text-slate-400">
                  IDS: {agent.ids_status || "n/a"}
                  {agent.last_heartbeat
                    ? ` · ${new Date(agent.last_heartbeat).toLocaleTimeString()}`
                    : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
