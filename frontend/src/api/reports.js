import client from "./client";

// Same blob approach as the incident-report helpers: the endpoint needs the
// bearer token, so fetch it, then either open or download the result.
export async function openSummaryReport() {
  const res = await client.get("/api/reports/summary", {
    responseType: "blob",
  });

  const url = URL.createObjectURL(res.data);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export async function downloadSummaryReport() {
  const res = await client.get("/api/reports/summary", {
    responseType: "blob",
  });

  const url = URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = "soc-summary-report.html";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
