import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";
import { createIncident } from "../api/incidents";
import { isLead } from "../api/auth";
import { SEVERITIES } from "../utils/severity";

const STATUS_OPTIONS = ["open", "investigating", "contained", "resolved", "closed"];

const EMPTY_FORM = {
  title: "",
  description: "",
  severity: "HIGH",
  category: "",
  sourceIps: "",
  affectedHosts: "",
  assignedTo: "",
};

function severityClasses(severity) {
  return ["high", "critical"].includes((severity || "").toLowerCase())
    ? "bg-red-950 text-red-300 border border-red-900"
    : "bg-amber-950 text-amber-300 border border-amber-900";
}

// "a, b, c" -> ["a", "b", "c"]; empty input -> undefined (field stays null).
function splitList(value) {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : undefined;
}

export default function IncidentsList() {
  const navigate = useNavigate();
  const lead = isLead();

  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState("");
  const [users, setUsers] = useState([]);

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

  function openCreate() {
    setForm(EMPTY_FORM);
    setCreateError("");
    setCreating(true);

    client
      .get("/api/users")
      .then((res) => setUsers(Array.isArray(res.data) ? res.data : []))
      .catch(() => setUsers([]));
  }

  async function handleCreate(event) {
    event.preventDefault();
    setSubmitting(true);
    setCreateError("");

    const payload = {
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      severity: form.severity,
      category: form.category.trim() || undefined,
      source_ips: splitList(form.sourceIps),
      affected_hosts: splitList(form.affectedHosts),
    };

    if (form.assignedTo) {
      payload.assigned_to = Number(form.assignedTo);
    }

    try {
      const res = await createIncident(payload);
      const id = res.data.incident_id ?? res.data.id;
      setCreating(false);
      navigate(`/incidents/${id}`);
    } catch (err) {
      setCreateError(err.response?.data?.detail || "Could not create the incident.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-400">Loading incidents...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Security Incidents</h1>
        <div className="flex gap-2">
          {lead && (
            <button
              type="button"
              onClick={openCreate}
              className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600"
            >
              New incident
            </button>
          )}
          <button
            type="button"
            onClick={fetchIncidents}
            className="rounded bg-slate-800 px-4 py-2 text-sm font-semibold hover:bg-slate-700"
          >
            Refresh
          </button>
        </div>
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

      {creating && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <form
            onSubmit={handleCreate}
            className="w-full max-w-lg space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-5"
          >
            <h2 className="text-lg font-semibold">New incident</h2>

            <label className="block text-sm">
              <span className="text-slate-400">Title (required)</span>
              <input
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                required
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
              />
            </label>

            <label className="block text-sm">
              <span className="text-slate-400">Description</span>
              <textarea
                value={form.description}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
                rows={2}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
              />
            </label>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="text-slate-400">Severity</span>
                <select
                  value={form.severity}
                  onChange={(event) => setForm({ ...form, severity: event.target.value })}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
                >
                  {SEVERITIES.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-sm">
                <span className="text-slate-400">Category</span>
                <input
                  value={form.category}
                  onChange={(event) => setForm({ ...form, category: event.target.value })}
                  placeholder="e.g. authentication"
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
                />
              </label>
            </div>

            <label className="block text-sm">
              <span className="text-slate-400">Source IPs (comma separated)</span>
              <input
                value={form.sourceIps}
                onChange={(event) => setForm({ ...form, sourceIps: event.target.value })}
                placeholder="203.0.113.5, 198.51.100.44"
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
              />
            </label>

            <label className="block text-sm">
              <span className="text-slate-400">Affected hosts (comma separated)</span>
              <input
                value={form.affectedHosts}
                onChange={(event) =>
                  setForm({ ...form, affectedHosts: event.target.value })
                }
                placeholder="web-01, db-01"
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
              />
            </label>

            {lead && (
              <label className="block text-sm">
                <span className="text-slate-400">Assign to</span>
                <select
                  value={form.assignedTo}
                  onChange={(event) => setForm({ ...form, assignedTo: event.target.value })}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
                >
                  <option value="">Unassigned</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.username} ({user.role})
                    </option>
                  ))}
                </select>
              </label>
            )}

            {createError && <p className="text-sm text-red-400">{createError}</p>}

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="rounded border border-slate-700 px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
              >
                {submitting ? "Creating..." : "Create incident"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
