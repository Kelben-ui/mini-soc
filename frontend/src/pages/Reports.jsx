import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getStats } from "../api/stats";
import { getIncidents, openIncidentReport, downloadIncidentReport } from "../api/incidents";
import { severityClasses } from "../utils/severity";
import { formatDateTime, formatDuration } from "../utils/format";

const POLL_MS = 15000;

function Tile({ label, value, accent }) {
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

export default function Reports() {
  const [stats, setStats] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    function fetchReports() {
      getStats()
        .then((res) => {
          if (!cancelled) setStats(res.data);
        })
        .catch(() => {
          if (!cancelled) setError("Could not load reporting statistics.");
        });

      getIncidents()
        .then((res) => {
          if (cancelled) return;
          const data = res.data;
          setIncidents(Array.isArray(data) ? data : data?.incidents || []);
        })
        .catch(() => {});
    }

    fetchReports();
    const interval = setInterval(fetchReports, POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const statsData = stats || {};
  const bySeverity = statsData.alerts_by_severity || {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Reports</h1>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Total alerts" value={statsData.total_alerts ?? "—"} />
        <Tile label="Total incidents" value={statsData.total_incidents ?? "—"} />
        <Tile label="Open incidents" value={statsData.open_incidents ?? "—"} />
        <Tile
          label="Threat level"
          value={statsData.threat_level || "—"}
          accent="text-amber-300"
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Tile
          label="Mean time to detect"
          value={formatDuration(statsData.mean_time_to_detect_seconds)}
        />
        <Tile
          label="Mean time to contain"
          value={formatDuration(statsData.mean_time_to_contain_seconds)}
        />
        <Tile
          label="Mean time to resolve"
          value={formatDuration(statsData.mean_time_to_resolve_seconds)}
        />
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Alerts by severity
        </h2>
        <div className="flex flex-wrap gap-3">
          {Object.entries(bySeverity).length === 0 ? (
            <p className="text-sm text-slate-500">No alerts recorded.</p>
          ) : (
            Object.entries(bySeverity).map(([severity, count]) => (
              <span
                key={severity}
                className={`rounded px-3 py-1 text-xs font-semibold uppercase ${severityClasses(
                  severity
                )}`}
              >
                {severity}: {count}
              </span>
            ))
          )}
        </div>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Incident reports
        </h2>

        {incidents.length === 0 ? (
          <p className="text-sm text-slate-500">No incidents recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[48rem] text-left text-sm">
              <thead className="bg-slate-950 text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-3 py-2">Code</th>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Severity</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Created</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {incidents.map((incident) => (
                  <tr key={incident.incident_id} className="hover:bg-slate-950/60">
                    <td className="px-3 py-2 font-mono text-xs">
                      <Link
                        to={`/incidents/${incident.incident_id}`}
                        className="text-sky-400 hover:underline"
                      >
                        {incident.incident_code}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{incident.title}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${severityClasses(
                          incident.severity
                        )}`}
                      >
                        {incident.severity}
                      </span>
                    </td>
                    <td className="px-3 py-2 uppercase text-slate-300">
                      {incident.status}
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-400">
                      {formatDateTime(incident.created_at)}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => openIncidentReport(incident.incident_id)}
                          className="rounded bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700"
                        >
                          View report
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            downloadIncidentReport(
                              incident.incident_id,
                              incident.incident_code
                            )
                          }
                          className="rounded bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700"
                        >
                          Download
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
