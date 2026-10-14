import client from "./client";

export function getStats() {
  return client.get("/api/stats");
}
