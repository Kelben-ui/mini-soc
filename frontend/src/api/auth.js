import client from "./client";

export async function login(username, password) {
  const res = await client.post("/api/auth/login", { username, password });
  const token = res.data.access_token;
  localStorage.setItem("jwt", token);

  const role = decodeRole(token);
  if (role) localStorage.setItem("role", role);

  return res.data;
}

function decodeRole(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.role || null;
  } catch {
    return null;
  }
}

export function logout() {
  localStorage.removeItem("jwt");
  localStorage.removeItem("role");
}

export function isLoggedIn() {
  return !!localStorage.getItem("jwt");
}

export function getRole() {
  return localStorage.getItem("role") || "user";
}
// src/api/auth.js — add this
export function canCloseIncident() {
  const role = getRole();
  return role === "lead" || role === "admin";
}