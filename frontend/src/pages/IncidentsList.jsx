import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import client from "../api/client";

const STATUS_OPTIONS = ["open", "investigating", "contained", "resolved", "closed"];

function severityClasses(severity) {
  return ["high", "critical"].includes((severity || "").toLowerCase())
    ? "bg-red-950 text-red-300 border border-red-900"
    : "bg-amber-950 text-amber-300 border border-amber-900";
}

export default function IncidentsList() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);

  function fetchIncidents() {
    setLoading(true);
    return client
      .get("/api/incidents")
      .then((res) =>
        setIncidents(Array.isArray(res.data) ? res.data : res.data?.incidents || [])
      )
      .catch(() => setError("Failed to load incidents list."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchIncidents();
  }, []);

  async function handleStatusChange(incidentId, newStatus) {
    setUpdatingId(incidentId);
    setError("");

    try {
      await client.patch(`/api/incidents/${incidentId}/status`, {
        status: newStatus,
        comment: "Status updated from incidents list",
      });

      setIncidents((current) =>
        current.map((incident) =>
          (incident.incident_id ?? incident.id) === incidentId
            ? { ...incident, status: newStatus }
            : incident
        )
      );
    } catch (err) {
      setError(err.response?.data?.detail || "Could not update the incident status.");
    } finally {
      setUpdatingId(null);
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-400">Loading incidents...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Security Incidents</h1>
        <button
          type="button"
          onClick={fetchIncidents}
          className="rounded bg-slate-800 px-4 py-2 text-sm font-semibold hover:bg-slate-700"
        >
          Refresh
        </button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full min-w-[48rem] text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {incidents.length === 0 ? (
              <tr>
                <td colSpan="5" className="px-4 py-8 text-center text-slate-500">
                  No incidents recorded.
                </td>
              </tr>
            ) : (
              incidents.map((incident) => {
                const id = incident.incident_id ?? incident.id;

                return (
                  <tr key={id} className="hover:bg-slate-900/60">
                    <td className="px-4 py-3 font-mono text-xs">
                      <Link
                        to={`/incidents/${id}`}
                        className="text-sky-400 hover:underline"
                      >
                        {incident.incident_code || id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${severityClasses(
                          incident.severity
                        )}`}
                      >
                        {incident.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {incident.title || incident.description || "N/A"}
                    </td>
                    <td className="px-4 py-3 capitalize">{incident.status}</td>
                    <td className="px-4 py-3">
                      <select
                        value={incident.status}
                        disabled={updatingId === id}
                        onChange={(event) => handleStatusChange(id, event.target.value)}
                        className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs"
                      >
                        {STATUS_OPTIONS.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
