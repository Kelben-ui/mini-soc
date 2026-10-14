import { useState } from "react";
import client from "../api/client";

const EMPTY_FILTERS = {
  src_ip: "",
  host: "",
  log_type: "",
  start_time: "",
  end_time: "",
};

function toIso(value) {
  if (!value) return undefined;
  return new Date(value).toISOString();
}

export default function EventSearch() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [events, setEvents] = useState([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function updateFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }));
  }

  async function handleSearch(event) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await client.get("/api/events", {
        params: {
          src_ip: filters.src_ip || undefined,
          host: filters.host || undefined,
          log_type: filters.log_type || undefined,
          start_time: toIso(filters.start_time),
          end_time: toIso(filters.end_time),
        },
      });

      setEvents(Array.isArray(res.data) ? res.data : res.data?.events || []);
      setSearched(true);
    } catch {
      setError("Could not search events. Check the backend connection.");
    } finally {
      setLoading(false);
    }
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
          value={filters.src_ip}
          onChange={(event) => updateFilter("src_ip", event.target.value)}
          placeholder="Source IP"
          className={inputClass}
        />
        <input
          type="text"
          value={filters.host}
          onChange={(event) => updateFilter("host", event.target.value)}
          placeholder="Host"
          className={inputClass}
        />
        <input
          type="text"
          value={filters.log_type}
          onChange={(event) => updateFilter("log_type", event.target.value)}
          placeholder="Log type (e.g. auth)"
          className={inputClass}
        />
        <label className="text-xs text-slate-400">
          From
          <input
            type="datetime-local"
            value={filters.start_time}
            onChange={(event) => updateFilter("start_time", event.target.value)}
            className={`mt-1 w-full ${inputClass}`}
          />
        </label>
        <label className="text-xs text-slate-400">
          To
          <input
            type="datetime-local"
            value={filters.end_time}
            onChange={(event) => updateFilter("end_time", event.target.value)}
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
            onClick={() => setFilters(EMPTY_FILTERS)}
            className="rounded border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
          >
            Clear
          </button>
        </div>
      </form>

      {error && <p className="text-sm text-red-400">{error}</p>}

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
                  {searched
                    ? "No events matched those filters."
                    : "Set filters and search to view events."}
                </td>
              </tr>
            ) : (
              events.map((event) => (
                <tr key={event.event_id} className="align-top hover:bg-slate-900/60">
                  <td className="px-3 py-3 text-xs text-slate-400">
                    {event.timestamp}
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
