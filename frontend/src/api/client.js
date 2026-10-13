import axios from "axios";

// Base URL is empty by default so every call is same-origin ("/api/..."),
// which works through the Vite dev proxy and the nginx /api proxy. Set
// VITE_API_BASE_URL only when the API is on a different origin.
const client = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || "" });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("jwt");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("jwt");
      localStorage.removeItem("role");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default client;
