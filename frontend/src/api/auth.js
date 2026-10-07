import client from "./client";

export async function login(username, password) {
  const res = await client.post("/api/auth/login", { username, password });
  localStorage.setItem("jwt", res.data.access_token); // confirm this field name in /docs first
  return res.data;
}
