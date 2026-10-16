import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addNote,
  downloadEvidence,
  getActions,
  getCustody,
  getEvidence,
  getIncident,
  getNotes,
  getTimeline,
  openIncidentReport,
  downloadIncidentReport,
  recordAction,
  updateIncident,
  updateIncidentStatus,
  uploadEvidence,
  verifyEvidence,
} from "../api/incidents";
import client from "../api/client";
import { getRole, isLead } from "../api/auth";
import { severityClasses } from "../utils/severity";
import { formatBytes, formatDateTime, formatDuration } from "../utils/format";

const BLOCK_ACTIONS = ["block ip", "block_ip", "block-ip", "block"];
const STATUS_OPTIONS = ["open", "investigating", "contained", "resolved", "closed"];
const ACTION_TYPES = [
  "block ip",
  "disable user",
  "isolate host",
  "reset password",
  "patch",
  "other",
];

function isBlockAction(actionType) {
  return BLOCK_ACTIONS.includes((actionType || "").trim().toLowerCase());
}

function statusClasses(status) {
  switch (status) {
    case "executed":
      return "bg-red-950 text-red-300";
    case "unblocked":
      return "bg-emerald-950 text-emerald-300";
    case "failed":
      return "bg-orange-950 text-orange-300";
    default:
      return "bg-slate-800 text-slate-300";
  }
}

function Metric({ label, seconds }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950 p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-100">
        {formatDuration(seconds)}
      </div>
    </div>
  );
}

function Panel({ title, children, actions }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

export default function IncidentDetail() {
  const { id } = useParams();
  const lead = isLead();
  const role = getRole();

  const [incident, setIncident] = useState(null);
  const [notes, setNotes] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [actions, setActions] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [custody, setCustody] = useState({});

  const [status, setStatus] = useState("");
  const [statusComment, setStatusComment] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [lessons, setLessons] = useState("");
  const [assignee, setAssignee] = useState("");
  const [users, setUsers] = useState([]);

  const [actionType, setActionType] = useState("block ip");
  const [actionTarget, setActionTarget] = useState("");
  const [actionReason, setActionReason] = useState("");

  const [confirm, setConfirm] = useState(null);
  const [confirmReason, setConfirmReason] = useState("");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const res = await getIncident(id);
      setIncident(res.data);
      setStatus(res.data.status);
      setRootCause(res.data.root_cause || "");
      setLessons(res.data.lessons_learned || "");
      setAssignee(res.data.assigned_to ?? "");

      const [notesRes, evidenceRes, actionsRes, timelineRes] = await Promise.all([
        getNotes(id),
        getEvidence(id),
        getActions(id),
        getTimeline(id),
      ]);

      setNotes(Array.isArray(notesRes.data) ? notesRes.data : []);
      setEvidence(Array.isArray(evidenceRes.data) ? evidenceRes.data : []);
      setActions(Array.isArray(actionsRes.data) ? actionsRes.data : []);
      setTimeline(timelineRes.data?.items || []);
    } catch {
      setError("Could not load this incident.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!lead) return;
    client
      .get("/api/users")
      .then((res) => setUsers(Array.isArray(res.data) ? res.data : []))
      .catch(() => {});
  }, [lead]);

  function flash(message) {
    setNotice(message);
    setError("");
  }

  async function submitStatus(event) {
    event.preventDefault();
    setBusy(true);

    try {
      await updateIncidentStatus(id, status, statusComment || "Status updated");
      setStatusComment("");
      await load();
      flash(`Status updated to ${status}.`);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not update the status.");
    } finally {
      setBusy(false);
    }
  }

  async function submitNote(event) {
    event.preventDefault();
    if (!noteBody.trim()) return;

    setBusy(true);

    try {
      await addNote(id, noteBody);
      setNoteBody("");
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not add the note.");
    } finally {
      setBusy(false);
    }
  }

  async function submitNarrative(event) {
    event.preventDefault();
    setBusy(true);

    try {
      await updateIncident(id, { root_cause: rootCause, lessons_learned: lessons });
      await load();
      flash("Root cause and lessons learned saved.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not save the incident.");
    } finally {
      setBusy(false);
    }
  }

  async function submitAssignment(event) {
    event.preventDefault();
    setBusy(true);

    try {
      await updateIncident(id, { assigned_to: Number(assignee) });
      await load();
      flash("Incident assignment updated.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not assign the incident.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setBusy(true);

    try {
      await uploadEvidence(id, file);
      event.target.value = "";
      await load();
      flash("Evidence uploaded and hashed.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not upload evidence.");
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify(item) {
    setBusy(true);

    try {
      const res = await verifyEvidence(item.id);
      flash(
        res.data.verified
          ? `Evidence #${item.id} verified (hash matches).`
          : `Evidence #${item.id} FAILED verification.`
      );
      await loadCustody(item.id);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not verify evidence.");
    } finally {
      setBusy(false);
    }
  }

  async function loadCustody(evidenceId) {
    const res = await getCustody(evidenceId);
    setCustody((current) => ({
      ...current,
      [evidenceId]: Array.isArray(res.data) ? res.data : [],
    }));
  }

  async function handleRecordAction(event) {
    event.preventDefault();
    setBusy(true);

    try {
      await recordAction(id, {
        action_type: actionType,
        target: actionTarget,
        reason: actionReason || "Recorded from the incident dashboard",
        result: "Recorded for analyst review",
      });
      setActionTarget("");
      setActionReason("");
      await load();
      flash("Response action recorded.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not record the action.");
    } finally {
      setBusy(false);
    }
  }

  async function submitConfirm(event) {
    event.preventDefault();
    if (!confirm) return;

    setBusy(true);

    try {
      const url =
        confirm.mode === "execute"
          ? `/api/actions/${confirm.action.id}/execute`
          : `/api/actions/${confirm.action.id}/unblock`;

      const res = await client.post(url, { confirm: true, reason: confirmReason });

      flash(
        res.data.success
          ? `${confirm.mode === "execute" ? "Blocked" : "Unblocked"} ${confirm.action.target}.`
          : `Action failed: ${res.data.message}`
      );
      setConfirm(null);
      setConfirmReason("");
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not perform the action.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="text-sm text-slate-400">Loading incident...</p>;
  if (error && !incident) return <p className="text-sm text-red-400">{error}</p>;
  if (!incident) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/incidents" className="text-sm text-slate-400 hover:text-slate-200">
          ← Incidents
        </Link>
        <h1 className="text-2xl font-bold">{incident.title}</h1>
        <span
          className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${severityClasses(
            incident.severity
          )}`}
        >
          {incident.severity}
        </span>
        <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-semibold uppercase">
          {incident.status}
        </span>
        <button
          type="button"
          onClick={() => downloadIncidentReport(id, incident.incident_code)}
          className="ml-auto rounded bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700"
        >
          Download report
        </button>
        <button
          type="button"
          onClick={() => openIncidentReport(id)}
          className="rounded bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700"
        >
          View report
        </button>
      </div>

      {notice && (
        <p className="rounded border border-emerald-900 bg-emerald-950 px-3 py-2 text-sm text-emerald-300">
          {notice}
        </p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}

      <section className="grid grid-cols-1 gap-4 rounded-lg border border-slate-800 bg-slate-900 p-4 lg:grid-cols-2">
        <div className="space-y-2 text-sm">
          <div className="font-mono text-slate-400">{incident.incident_code}</div>
          <div className="text-slate-200">{incident.description || "No description."}</div>
          <div className="text-slate-400">
            Source IPs: {incident.source_ips?.join(", ") || "—"}
          </div>
          <div className="text-slate-400">
            Affected hosts: {incident.affected_hosts?.join(", ") || "—"}
          </div>
          <div className="text-slate-400">
            Created: {formatDateTime(incident.created_at)}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <Metric label="TTD" seconds={incident.ttd_seconds} />
          <Metric label="TTC" seconds={incident.ttc_seconds} />
          <Metric label="TTR" seconds={incident.ttr_seconds} />
        </div>
      </section>

      {lead && (
        <Panel title="Update status">
          <form onSubmit={submitStatus} className="flex flex-wrap items-end gap-3">
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <input
              value={statusComment}
              onChange={(event) => setStatusComment(event.target.value)}
              placeholder="Comment (required by the API)"
              className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
            >
              Save
            </button>
          </form>
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title={`Timeline (${timeline.length})`}>
          {timeline.length === 0 ? (
            <p className="text-sm text-slate-500">No timeline entries yet.</p>
          ) : (
            <ol className="space-y-3 border-l border-slate-800 pl-4">
              {timeline.map((item, index) => (
                <li key={`${item.type}-${index}`} className="text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-xs uppercase text-slate-300">
                      {item.type}
                    </span>
                    <span className="text-slate-200">{item.summary}</span>
                    <span className="ml-auto text-xs text-slate-500">
                      {formatDateTime(item.timestamp)}
                    </span>
                  </div>
                  {item.details && (
                    <p className="mt-1 text-xs text-slate-400">{item.details}</p>
                  )}
                  {item.actor && (
                    <p className="text-xs text-slate-500">by {item.actor}</p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </Panel>

        <Panel title={`Notes (${notes.length})`}>
          <form onSubmit={submitNote} className="mb-3 space-y-2">
            <textarea
              value={noteBody}
              onChange={(event) => setNoteBody(event.target.value)}
              rows={2}
              placeholder="Add an investigation note..."
              className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={busy || !noteBody.trim()}
              className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
            >
              Add note
            </button>
          </form>

          {notes.length === 0 ? (
            <p className="text-sm text-slate-500">No notes yet.</p>
          ) : (
            <ul className="space-y-2">
              {notes.map((note) => (
                <li key={note.id} className="rounded bg-slate-950 p-3 text-sm">
                  <p className="text-slate-200">{note.body}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {formatDateTime(note.created_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel
        title={`Evidence (${evidence.length})`}
        actions={
          <label className="cursor-pointer rounded bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700">
            Upload evidence
            <input type="file" onChange={handleUpload} className="hidden" />
          </label>
        }
      >
        {evidence.length === 0 ? (
          <p className="text-sm text-slate-500">No evidence uploaded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[48rem] text-left text-sm">
              <thead className="bg-slate-950 text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-3 py-2">File</th>
                  <th className="px-3 py-2">Size</th>
                  <th className="px-3 py-2">SHA-256</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {evidence.map((item) => (
                  <tr key={item.id} className="align-top">
                    <td className="px-3 py-2">
                      <div className="text-slate-200">{item.filename}</div>
                      <div className="text-xs text-slate-500">
                        {formatDateTime(item.uploaded_at)}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-slate-400">
                      {formatBytes(item.size_bytes)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-400">
                      {item.sha256?.slice(0, 16)}…
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => handleVerify(item)}
                          disabled={busy}
                          className="rounded bg-slate-800 px-2 py-1 text-xs font-semibold hover:bg-slate-700 disabled:opacity-40"
                        >
                          Verify
                        </button>
                        <button
                          type="button"
                          onClick={() => downloadEvidence(item.id, item.filename)}
                          className="rounded bg-slate-800 px-2 py-1 text-xs font-semibold hover:bg-slate-700"
                        >
                          Download
                        </button>
                        <button
                          type="button"
                          onClick={() => loadCustody(item.id)}
                          className="rounded bg-slate-800 px-2 py-1 text-xs font-semibold hover:bg-slate-700"
                        >
                          Custody
                        </button>
                      </div>

                      {custody[item.id] && (
                        <ul className="mt-2 space-y-1 text-xs text-slate-400">
                          {custody[item.id].length === 0 ? (
                            <li>No custody entries.</li>
                          ) : (
                            custody[item.id].map((entry) => (
                              <li key={entry.id}>
                                {formatDateTime(entry.timestamp)} · {entry.action}
                                {entry.notes ? ` — ${entry.notes}` : ""}
                              </li>
                            ))
                          )}
                        </ul>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {lead && (
        <Panel title="Response actions">
          <form
            onSubmit={handleRecordAction}
            className="mb-3 flex flex-wrap items-end gap-3"
          >
            <select
              value={actionType}
              onChange={(event) => setActionType(event.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            >
              {ACTION_TYPES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <input
              value={actionTarget}
              onChange={(event) => setActionTarget(event.target.value)}
              placeholder="Target (e.g. 203.0.113.5)"
              required
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <input
              value={actionReason}
              onChange={(event) => setActionReason(event.target.value)}
              placeholder="Reason"
              className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-slate-800 px-4 py-2 text-sm font-semibold hover:bg-slate-700 disabled:opacity-40"
            >
              Record
            </button>
          </form>

          {actions.length === 0 ? (
            <p className="text-sm text-slate-500">No response actions recorded.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950 text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-3 py-2">Action</th>
                  <th className="px-3 py-2">Target</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Result</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {actions.map((action) => (
                  <tr key={action.id} className="align-top">
                    <td className="px-3 py-2">{action.action_type}</td>
                    <td className="px-3 py-2 font-mono text-xs">{action.target}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${statusClasses(
                          action.status
                        )}`}
                      >
                        {action.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-300">{action.result}</td>
                    <td className="px-3 py-2">
                      {isBlockAction(action.action_type) && action.status !== "executed" && (
                        <button
                          type="button"
                          onClick={() => setConfirm({ action, mode: "execute" })}
                          className="rounded bg-red-700 px-3 py-1 text-xs font-semibold hover:bg-red-600"
                        >
                          Block IP
                        </button>
                      )}
                      {isBlockAction(action.action_type) &&
                        action.status === "executed" && (
                          <button
                            type="button"
                            onClick={() => setConfirm({ action, mode: "unblock" })}
                            className="rounded bg-slate-700 px-3 py-1 text-xs font-semibold hover:bg-slate-600"
                          >
                            Unblock
                          </button>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Root cause & lessons learned">
          <form onSubmit={submitNarrative} className="space-y-3">
            <label className="block text-sm">
              <span className="text-slate-400">Root cause</span>
              <textarea
                value={rootCause}
                onChange={(event) => setRootCause(event.target.value)}
                rows={3}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-400">Lessons learned</span>
              <textarea
                value={lessons}
                onChange={(event) => setLessons(event.target.value)}
                rows={3}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
            >
              Save
            </button>
          </form>
        </Panel>

        <Panel title="Assignment">
          {lead ? (
            <form onSubmit={submitAssignment} className="flex flex-wrap items-end gap-3">
              <select
                value={assignee}
                onChange={(event) => setAssignee(event.target.value)}
                className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              >
                <option value="">Unassigned</option>
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
          ) : (
            <p className="text-sm text-slate-400">
              Assigned to: {incident.assigned_to ?? "Unassigned"} (role: {role})
            </p>
          )}
        </Panel>
      </div>

      {confirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <form
            onSubmit={submitConfirm}
            className="w-full max-w-md space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-5"
          >
            <h2 className="text-lg font-semibold">
              {confirm.mode === "execute" ? "Confirm block" : "Confirm unblock"}
            </h2>
            <p className="text-sm text-slate-300">
              {confirm.mode === "execute"
                ? `Block ${confirm.action.target}? This changes the firewall and is logged.`
                : `Remove the block on ${confirm.action.target}?`}
            </p>
            <label className="block text-sm">
              <span className="text-slate-400">Reason</span>
              <input
                value={confirmReason}
                onChange={(event) => setConfirmReason(event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </label>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirm(null)}
                className="rounded border border-slate-700 px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy}
                className={`rounded px-4 py-2 text-sm font-semibold disabled:opacity-40 ${
                  confirm.mode === "execute"
                    ? "bg-red-700 hover:bg-red-600"
                    : "bg-sky-700 hover:bg-sky-600"
                }`}
              >
                {confirm.mode === "execute" ? "Block IP" : "Unblock"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
