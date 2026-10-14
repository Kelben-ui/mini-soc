import client from "./client";

export const getAlerts = (params = {}) => client.get("/api/alerts", { params });
export const getAlert = (id) => client.get(`/api/alerts/${id}`);
export const updateAlert = (id, body) => client.patch(`/api/alerts/${id}`, body);
export const promoteAlert = (id) => client.post(`/api/alerts/${id}/promote`);
export const exportAlertEvidence = (id) =>
  client.post(`/api/alerts/${id}/export-evidence`);
