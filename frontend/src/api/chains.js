import client from "./client";

export function getChains(params = {}) {
  return client.get("/api/chains", { params });
}

export function getChain(chainId) {
  return client.get(`/api/chains/${chainId}`);
}

export function promoteChain(chainId) {
  return client.post(`/api/chains/${chainId}/promote`);
}
