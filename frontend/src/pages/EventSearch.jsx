import { useEffect, useState } from "react";
import client from "../api/client";
import { formatDateTime } from "../utils/format";

const EMPTY_FILTERS = {
  src_ip: "",
  host: "",
  log_type: "",
  start_time: "",
  end_time: "",
};

const PAGE_SIZE = 100;
const POLL_MS = 8000; // under the spec's 10s live-update requirement

function toIso(value) {
  if (!value) return undefined;
  return new Date(value).toISOString();
}

export default function EventSearch() {
  // The form holds "draft" values; only pressing Search copies them into
  // "applied", which drives the fetch (and the live poll).  This keeps the
  // page searchable while still auto-loading and refreshing like AlertsList.
  const [draft, setDraft] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const { src_ip, host, log_type, start_time, end_time } = applied;

  useEffect(() => {
    let cancelled = false;

    function fetchEvents() {
      setLoading(true);

      client
        .get("/api/events", {
          params: {
            src_ip: src_ip || undefined,
            host: host || undefined,
            log_type: log_type || undefined,
            start_time: toIso(start_time),
            end_time: toIso(end_time),
            limit: PAGE_SIZE,
            offset,
          },
        })
        .then((res) => {
          if (cancelled) return;
          const payload = res.data || {};
          setEvents(Array.isArray(res.data) ? res.data : payload.items || []);
          setTotal(res.data?.total ?? 0);
          setError("");
        })
        .catch(() => {
          if (!cancelled) {
            setError("Could not search events. Check the backend connection.");
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }

    fetchEvents();
    const interval = setInterval(fetchEvents, POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [src_ip, host, log_type, start_time, end_time, offset]);

  function updateDraft(name, value) {
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function handleSearch(event) {
    event.preventDefault();
    setOffset(0);
    setApplied(draft);
  }

  function handleClear() {
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setOffset(0);
    setError("");
  }

  const inputClass =
    "rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder:text-slate-500";

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Event &amp; Log Search</h1>

      <form
        onSubmit={handleSearch}
        className="grid grid-cols-1 gap-3 rounded-lg border border-slate-800 bg-slate-900 p-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        <input
          type="text"
          value={draft.src_ip}
          onChange={(event) => updateDraft("src_ip", event.target.value)}
          placeholder="Source IP"
          className={inputClass}
        />
        <input
          type="text"
          value={draft.host}
          onChange={(event) => updateDraft("host", event.target.value)}
          placeholder="Host"
          className={inputClass}
        />
        <input
          type="text"
          value={draft.log_type}
          onChange={(event) => updateDraft("log_type", event.target.value)}
          placeholder="Log type (e.g. auth)"
          className={inputClass}
        />
        <label className="text-xs text-slate-400">
          From
          <input
            type="datetime-local"
            value={draft.start_time}
            onChange={(event) => updateDraft("start_time", event.target.value)}
            className={`mt-1 w-full ${inputClass}`}
          />
        </label>
        <label className="text-xs text-slate-400">
          To
          <input
            type="datetime-local"
            value={draft.end_time}
            onChange={(event) => updateDraft("end_time", event.target.value)}
            className={`mt-1 w-full ${inputClass}`}
          />
        </label>
        <div className="flex items-end gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
          >
            {loading ? "Searching..." : "Search"}
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="rounded border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
          >
            Clear
          </button>
        </div>
      </form>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <p className="text-sm text-slate-400">
        {total > 0
          ? `Showing ${offset + 1}–${offset + events.length} of ${total} events (live, refreshes every 8s).`
          : "No events match these filters."}
      </p>

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full min-w-[64rem] text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-3 py-3">Timestamp</th>
              <th className="px-3 py-3">Host</th>
              <th className="px-3 py-3">Log type</th>
              <th className="px-3 py-3">Source</th>
              <th className="px-3 py-3">Destination</th>
              <th className="px-3 py-3">Action</th>
              <th className="px-3 py-3">Outcome</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {events.length === 0 ? (
              <tr>
                <td colSpan="7" className="px-3 py-8 text-center text-slate-500">
                  {loading ? "Loading events..." : "No events matched those filters."}
                </td>
              </tr>
            ) : (
              events.map((event) => (
                <tr key={event.event_id} className="align-top hover:bg-slate-900/60">
                  <td className="px-3 py-3 text-xs text-slate-400">
                    {formatDateTime(event.timestamp)}
                  </td>
                  <td className="px-3 py-3">{event.host}</td>
                  <td className="px-3 py-3">{event.log_type}</td>
                  <td className="px-3 py-3 font-mono text-xs">
                    {event.src_ip}
                    {event.src_port ? `:${event.src_port}` : ""}
                  </td>
                  <td className="px-3 py-3 font-mono text-xs">
                    {event.dst_ip}
                    {event.dst_port ? `:${event.dst_port}` : ""}
                  </td>
                  <td className="px-3 py-3">{event.action}</td>
                  <td className="px-3 py-3">{event.outcome}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > 0 && (
        <div className="flex items-center justify-between">
          <button
            type="button"
            disabled={offset <= 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="rounded border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800 disabled:opacity-40"
          >
            ← Previous
          </button>
          <span className="text-xs text-slate-500">
            Page {Math.floor(offset / PAGE_SIZE) + 1}
          </span>
          <button
            type="button"
            disabled={offset + events.length >= total || loading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="rounded border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}

      {events.length > 0 && (
        <details className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <summary className="cursor-pointer text-sm text-slate-400">
            Raw log lines ({events.length})
          </summary>
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs text-slate-300">
            {events.map((event) => event.raw).join("\n")}
          </pre>
        </details>
      )}
    </div>
  );
}
