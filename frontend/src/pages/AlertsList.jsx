import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAlerts } from "../api/alerts";
import { playbookFor } from "../playbookMap";
import { formatDateTime } from "../utils/format";

const SEVERITY_OPTIONS = ["", "LOW", "MEDIUM", "HIGH", "CRITICAL"];
const STATUS_OPTIONS = [
  "",
  "NEW",
  "INVESTIGATING",
  "CONTAINED",
  "RESOLVED",
  "FALSE POSITIVE",
];

const PAGE_SIZE = 25;
const POLL_MS = 8000; // under the spec's 10s live-update requirement

function severityClasses(severity) {
  switch ((severity || "").toUpperCase()) {
    case "CRITICAL":
      return "bg-red-950 text-red-300 border border-red-900";
    case "HIGH":
      return "bg-orange-950 text-orange-300 border border-orange-900";
    case "MEDIUM":
      return "bg-amber-950 text-amber-300 border border-amber-900";
    case "LOW":
      return "bg-sky-950 text-sky-300 border border-sky-900";
    default:
      return "bg-slate-800 text-slate-300 border border-slate-700";
  }
}

function statusClasses(status) {
  switch ((status || "").toUpperCase()) {
    case "NEW":
      return "bg-slate-800 text-slate-200";
    case "INVESTIGATING":
      return "bg-sky-950 text-sky-300";
    case "CONTAINED":
      return "bg-emerald-950 text-emerald-300";
    case "RESOLVED":
      return "bg-slate-700 text-slate-200";
    case "FALSE POSITIVE":
      return "bg-slate-800 text-slate-400";
    default:
      return "bg-slate-800 text-slate-300";
  }
}

const EMPTY_FILTERS = {
  severity: "",
  status: "",
  srcIp: "",
  ruleId: "",
  startTime: "",
  endTime: "",
};

function toIso(value) {
  if (!value) return undefined;
  return new Date(value).toISOString();
}

export default function AlertsList() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [error, setError] = useState("");

  const { severity, status, srcIp, ruleId, startTime, endTime } = filters;

  useEffect(() => {
    let cancelled = false;

    function fetchAlerts() {
      getAlerts({
        severity: severity || undefined,
        status: status || undefined,
        src_ip: srcIp || undefined,
        rule_id: ruleId || undefined,
        start_time: toIso(startTime),
        end_time: toIso(endTime),
        limit: PAGE_SIZE,
        offset,
      })
        .then((res) => {
          if (cancelled) return;
          setData({
            items: res.data?.items || [],
            total: res.data?.total || 0,
          });
          setError("");
        })
        .catch(() => {
          if (!cancelled) {
            setError("Could not load alerts. Check the backend connection.");
          }
        });
    }

    fetchAlerts();
    const interval = setInterval(fetchAlerts, POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [severity, status, srcIp, ruleId, startTime, endTime, offset]);

  function updateFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }));
    setOffset(0);
  }

  const { items, total } = data;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Alerts</h1>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <select
          value={severity}
          onChange={(event) => updateFilter("severity", event.target.value)}
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
        >
          {SEVERITY_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option || "All severities"}
            </option>
          ))}
        </select>

        <select
          value={status}
          onChange={(event) => updateFilter("status", event.target.value)}
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option || "All statuses"}
            </option>
          ))}
        </select>

        <input
          value={ruleId}
          onChange={(event) => updateFilter("ruleId", event.target.value)}
          placeholder="Rule ID (e.g. SSH-BF-001)"
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm placeholder:text-slate-500"
        />

        <input
          value={srcIp}
          onChange={(event) => updateFilter("srcIp", event.target.value)}
          placeholder="Source IP"
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm placeholder:text-slate-500"
        />

        <label className="text-xs text-slate-400">
          From
          <input
            type="datetime-local"
            value={startTime}
            onChange={(event) => updateFilter("startTime", event.target.value)}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          />
        </label>

        <label className="text-xs text-slate-400">
          To
          <input
            type="datetime-local"
            value={endTime}
            onChange={(event) => updateFilter("endTime", event.target.value)}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          />
        </label>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full min-w-[58rem] text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Source IP</th>
              <th className="px-4 py-3">Last seen</th>
              <th className="px-4 py-3">Playbook</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {items.length === 0 ? (
              <tr>
                <td colSpan="7" className="px-4 py-8 text-center text-slate-500">
                  No alerts match these filters.
                </td>
              </tr>
            ) : (
              items.map((alert) => (
                <tr key={alert.alert_id} className="hover:bg-slate-900/60">
                  <td className="px-4 py-3">
                    <Link
                      to={`/alerts/${alert.alert_id}`}
                      className="text-sky-400 hover:underline"
                    >
                      {alert.alert_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{alert.title}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold ${severityClasses(
                        alert.severity
                      )}`}
                    >
                      {alert.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold ${statusClasses(
                        alert.status
                      )}`}
                    >
                      {alert.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{alert.src_ip}</td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {formatDateTime(alert.last_seen)}
                  </td>
                  <td className="px-4 py-3">
                    <a
                      href={`/playbooks/${playbookFor(alert.rule_id)}`}
                      target="_blank"
                      rel="noreferrer"
                      title={`Response playbook for ${alert.rule_id}`}
                      className="inline-flex items-center gap-1.5 text-xs text-sky-400 hover:underline"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
                      </svg>
                      Playbook
                    </a>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <span className="text-slate-400">
          Page {page} of {pageCount} · {total} alerts
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
            className="rounded border border-slate-700 px-3 py-1 disabled:opacity-40"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset((current) => current + PAGE_SIZE)}
            className="rounded border border-slate-700 px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
