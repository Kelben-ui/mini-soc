import client from "./client";

export function getRules() {
  return client.get("/api/rules");
}
