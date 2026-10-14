import client from "./client";

export function getUsers() {
  return client.get("/api/users");
}

export function createUser(payload) {
  return client.post("/api/users", payload);
}

export function updateUserRole(userId, role) {
  return client.patch(`/api/users/${userId}`, { role });
}

export function resetUserPassword(userId, password) {
  return client.post(`/api/users/${userId}/password`, { password });
}
