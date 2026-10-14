import client from "../api/client";

export function getIncidents() {
  return client.get("/api/incidents");
}

export function getIncident(id) {
  return client.get(`/api/incidents/${id}`);
}

export function updateIncident(id, payload) {
  return client.patch(`/api/incidents/${id}`, payload);
}

export function updateIncidentStatus(id, status, comment) {
  return client.patch(`/api/incidents/${id}/status`, { status, comment });
}

export function getActions(id) {
  return client.get(`/api/incidents/${id}/actions`);
}

export function recordAction(id, action) {
  return client.post(`/api/incidents/${id}/actions`, action);
}

export function executeAction(actionId, reason) {
  return client.post(`/api/actions/${actionId}/execute`, { confirm: true, reason });
}

export function unblockAction(actionId, reason) {
  return client.post(`/api/actions/${actionId}/unblock`, { confirm: true, reason });
}

export function getNotes(id) {
  return client.get(`/api/incidents/${id}/notes`);
}

export function addNote(id, body) {
  return client.post(`/api/incidents/${id}/notes`, { body });
}

export function getEvidence(id) {
  return client.get(`/api/incidents/${id}/evidence`);
}

export function uploadEvidence(id, file) {
  const form = new FormData();
  form.append("file", file);
  return client.post(`/api/incidents/${id}/evidence`, form);
}

export function verifyEvidence(evidenceId) {
  return client.post(`/api/evidence/${evidenceId}/verify`);
}

export function getCustody(evidenceId) {
  return client.get(`/api/evidence/${evidenceId}/custody`);
}

export async function downloadEvidence(evidenceId, filename) {
  const res = await client.get(`/api/evidence/${evidenceId}/download`, {
    responseType: "blob",
  });

  const url = URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || `evidence-${evidenceId}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function getTimeline(id) {
  return client.get(`/api/incidents/${id}/timeline`);
}

export function reportUrl(id) {
  return `/api/incidents/${id}/report`;
}

// The report endpoint needs the bearer token, so fetch it as a blob and open
// the resulting object URL rather than navigating to the raw path.
export async function openIncidentReport(id) {
  const res = await client.get(`/api/incidents/${id}/report`, {
    responseType: "blob",
  });

  const url = URL.createObjectURL(res.data);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
