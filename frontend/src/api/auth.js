import client from "./client";

export async function login(username, password) {
  const res = await client.post("/api/auth/login", { username, password });
  const token = res.data.access_token;
  localStorage.setItem("jwt", token);

  const role = decodeRole(token);
  if (role) {
    localStorage.setItem("role", role);
  }

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
  return Boolean(localStorage.getItem("jwt"));
}

export function getRole() {
  return localStorage.getItem("role") || "user";
}

// The JWT carries the user id in `sub`; the Users page uses it to stop an admin
// from deactivating their own account (the backend enforces this too).
export function getUserId() {
  const token = localStorage.getItem("jwt");
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.sub != null ? Number(payload.sub) : null;
  } catch {
    return null;
  }
}

// Leads/admins are the only backend roles allowed to close incidents, change
// an alert's status and export alert evidence. The backend stays the security
// boundary; this only hides controls the user cannot use.
export function isLead() {
  const role = getRole();
  return role === "lead" || role === "admin";
}

export { isLead as canCloseIncident };
