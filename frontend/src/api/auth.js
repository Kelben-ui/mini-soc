import client from "./client";

export async function login(username, password) {
  const res = await client.post("/api/auth/login", { username, password });
  localStorage.setItem("jwt", res.data.access_token); // confirmed this field name in /docs
  return res.data;
}

export function logout() {
  localStorage.removeItem("jwt");
}

export function isLoggedIn() {
  return !!localStorage.getItem("jwt");
}

export function getRole() {
  return localStorage.getItem("role") || "user";
}
