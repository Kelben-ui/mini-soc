import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import client from "../api/client";
import {
  exportAlertEvidence,
  getAlert,
  promoteAlert,
  updateAlert,
} from "../api/alerts";
import { isLead } from "../api/auth";
import { PLAYBOOK_MAP } from "../playbookMap";
import { formatDateTime } from "../utils/format";

const STATUS_OPTIONS = [
  "NEW",
  "INVESTIGATING",
  "CONTAINED",
  "RESOLVED",
  "FALSE POSITIVE",
];

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

function Field({ label, children }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-sm text-slate-200">{children ?? "—"}</div>
    </div>
  );
}

export default function AlertDetail() {
  const { id } = useParams();
  const lead = isLead();

  const [alert, setAlert] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [playbook, setPlaybook] = useState("");

  const [users, setUsers] = useState([]);
  const [assignee, setAssignee] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [newStatus, setNewStatus] = useState("INVESTIGATING");
  const [comment, setComment] = useState("");
  const [reason, setReason] = useState("");

  function load() {
    return getAlert(id)
      .then((res) => {
        setAlert(res.data);
        setNewStatus(res.data.status || "INVESTIGATING");
        setAssignee(res.data.assigned_to ?? "");
      })
      .catch(() => setError("Could not load this alert."));
  }

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    if (!lead) return;
    client
      .get("/api/users")
      .then((res) => setUsers(Array.isArray(res.data) ? res.data : []))
      .catch(() => {});
  }, [lead]);

  useEffect(() => {
    if (!alert) return;

    const filename = PLAYBOOK_MAP[alert.rule_id];

    if (!filename) {
      setPlaybook("No playbook mapped for this rule.");
      return;
    }

    fetch(`/playbooks/${filename}`)
      .then((res) => res.text())
      .then(setPlaybook)
      .catch(() => setPlaybook("Could not load playbook."));
  }, [alert]);

  function flash(message) {
    setNotice(message);
    setError("");
  }

  async function submitStatus(event) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const body = { status: newStatus, comment };

      if (newStatus === "FALSE POSITIVE") {
        body.reason = reason;
      }

      await updateAlert(id, body);
      setDialogOpen(false);
      setComment("");
      setReason("");
      await load();
      flash(`Status updated to ${newStatus}.`);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not update the status.");
    } finally {
      setBusy(false);
    }
  }

  async function submitAssignment(event) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      await updateAlert(id, { assigned_to: Number(assignee) });
      await load();
      flash("Alert assignment updated.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not assign the alert.");
    } finally {
      setBusy(false);
    }
  }

  async function handlePromote() {
    if (!window.confirm("Promote this alert to an incident?")) return;

    setBusy(true);
    setError("");

    try {
      const res = await promoteAlert(id);
      await load();
      flash(`Incident ${res.data.incident_code} created.`);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not promote the alert.");
    } finally {
      setBusy(false);
    }
  }

  async function handleExport() {
    setBusy(true);
    setError("");

    try {
      const res = await exportAlertEvidence(id);
      flash(
        `Evidence #${res.data.evidence_id} recorded (${res.data.event_count} events).`
      );
    } catch (err) {
      setError(err.response?.data?.detail || "Could not export evidence.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !alert) {
    return <p className="text-sm text-red-400">{error}</p>;
  }

  if (!alert) {
    return <p className="text-sm text-slate-400">Loading alert...</p>;
  }

  const events = alert.events || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/alerts" className="text-sm text-slate-400 hover:text-slate-200">
          ← Alerts
        </Link>
        <h1 className="text-2xl font-bold">{alert.title}</h1>
        <span
          className={`rounded px-2 py-0.5 text-xs font-semibold ${severityClasses(
            alert.severity
          )}`}
        >
          {alert.severity}
        </span>
      </div>

      {notice && (
        <p className="rounded border border-emerald-900 bg-emerald-950 px-3 py-2 text-sm text-emerald-300">
          {notice}
        </p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}

      <section className="grid grid-cols-1 gap-4 rounded-lg border border-slate-800 bg-slate-900 p-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Alert ID">{alert.alert_id}</Field>
        <Field label="Rule">{alert.rule_id}</Field>
        <Field label="Status">
          <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-semibold">
            {alert.status}
          </span>
        </Field>
        <Field label="Source IP">{alert.src_ip}</Field>
        <Field label="Destination IP">{alert.dst_ip}</Field>
        <Field label="Destination host">{alert.dst_host}</Field>
        <Field label="Category">{alert.category}</Field>
        <Field label="MITRE">{alert.mitre}</Field>
        <Field label="Event count">{alert.count}</Field>
        <Field label="Chain ID">{alert.chain_id}</Field>
        <Field label="Assigned to">{alert.assigned_to}</Field>
        <Field label="Incident">
          {alert.incident_id ? (
            <Link
              to={`/incidents/${alert.incident_id}`}
              className="text-sky-400 hover:underline"
            >
              {alert.incident_id}
            </Link>
          ) : (
            "Not promoted"
          )}
        </Field>
        <Field label="First seen">{formatDateTime(alert.first_seen)}</Field>
        <Field label="Last seen">{formatDateTime(alert.last_seen)}</Field>
      </section>

      <section className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handlePromote}
          disabled={busy || Boolean(alert.incident_id)}
          className="rounded bg-slate-800 px-4 py-2 text-sm font-semibold hover:bg-slate-700 disabled:opacity-40"
        >
          {alert.incident_id ? "Already promoted" : "Promote to incident"}
        </button>

        {lead && (
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600"
          >
            Change status
          </button>
        )}

        {lead && (
          <button
            type="button"
            onClick={handleExport}
            disabled={busy}
            className="rounded bg-slate-800 px-4 py-2 text-sm font-semibold hover:bg-slate-700 disabled:opacity-40"
          >
            Export evidence
          </button>
        )}
      </section>

      {lead && (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Assign analyst
          </h2>
          <form onSubmit={submitAssignment} className="flex flex-wrap items-end gap-3">
            <select
              value={assignee}
              onChange={(event) => setAssignee(event.target.value)}
              required
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            >
              <option value="">Select an analyst</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.username} ({user.role})
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
            >
              Assign
            </button>
          </form>
        </section>
      )}

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Linked raw events ({events.length})
        </h2>

        {events.length === 0 ? (
          <p className="text-sm text-slate-500">No events linked to this alert.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <thead className="bg-slate-950 text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-3 py-2">Timestamp</th>
                  <th className="px-3 py-2">Host</th>
                  <th className="px-3 py-2">Log type</th>
                  <th className="px-3 py-2">Src</th>
                  <th className="px-3 py-2">Dst</th>
                  <th className="px-3 py-2">User</th>
                  <th className="px-3 py-2">Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {events.map((event) => (
                  <tr key={event.event_id}>
                    <td className="px-3 py-2 text-xs text-slate-400">
                      {formatDateTime(event.timestamp)}
                    </td>
                    <td className="px-3 py-2">{event.host}</td>
                    <td className="px-3 py-2">{event.log_type}</td>
                    <td className="px-3 py-2 font-mono text-xs">{event.src_ip}</td>
                    <td className="px-3 py-2 font-mono text-xs">{event.dst_ip}</td>
                    <td className="px-3 py-2">{event.user}</td>
                    <td className="px-3 py-2">{event.outcome}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-slate-400">
                Raw log lines
              </summary>
              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-3 text-xs text-slate-300">
                {events.map((event) => event.raw).join("\n")}
              </pre>
            </details>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Response playbook
        </h2>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs text-slate-300">
          {playbook}
        </pre>
      </section>

      {dialogOpen && lead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <form
            onSubmit={submitStatus}
            className="w-full max-w-md space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-5"
          >
            <h2 className="text-lg font-semibold">Change alert status</h2>

            <label className="block text-sm">
              <span className="text-slate-400">New status</span>
              <select
                value={newStatus}
                onChange={(event) => setNewStatus(event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm">
              <span className="text-slate-400">Comment (required)</span>
              <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                required
                rows={3}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
              />
            </label>

            {newStatus === "FALSE POSITIVE" && (
              <label className="block text-sm">
                <span className="text-slate-400">Reason (required)</span>
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  required
                  rows={2}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2"
                />
              </label>
            )}

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setDialogOpen(false)}
                className="rounded border border-slate-700 px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy}
                className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
              >
                Save status
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
