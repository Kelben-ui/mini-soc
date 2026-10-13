import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAlerts } from "../api/alerts";

const SEVERITY_OPTIONS = ["", "LOW", "MEDIUM", "HIGH", "CRITICAL"];
const STATUS_OPTIONS = ["", "NEW", "INVESTIGATING", "CONTAINED", "RESOLVED", "FALSE POSITIVE"];

export default function AlertsList() {
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;

    function fetchAlerts() {
      const params = {};
      if (severity) params.severity = severity;
      if (status) params.status = status;

      getAlerts(params)
        .then((res) => {
          if (!cancelled) {
            // handles either a plain array or a wrapped { alerts: [...] } shape
            setAlerts(Array.isArray(res.data) ? res.data : res.data.alerts || []);
            setError("");
          }
        })
        .catch(() => {
          if (!cancelled) setError("Could not load alerts. Check the backend connection.");
        });
    }

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 8000); // under the spec's 10s live-update requirement

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [severity, status]);

  function badgeClass(sev) {
    return `badge badge-${(sev || "").toLowerCase()}`;
  }

  return (
    <div>
      <h1 className="page-title">Alerts</h1>

      <div className="form-inline" style={{ marginBottom: 16 }}>
        <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>{s || "All severities"}</option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s || "All statuses"}</option>
          ))}
        </select>
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Source IP</th>
              <th>Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.alert_id}>
                <td><Link to={`/alerts/${a.alert_id}`}>{a.alert_id}</Link></td>
                <td style={{ fontFamily: "var(--font-ui)" }}>{a.title}</td>
                <td><span className={badgeClass(a.severity)}>{a.severity}</span></td>
                <td><span className="badge badge-status">{a.status}</span></td>
                <td>{a.src_ip}</td>
                <td>{a.last_seen}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {alerts.length === 0 && !error && (
          <p className="muted" style={{ padding: 16 }}>No alerts match these filters.</p>
        )}
      </div>
    </div>
  );
}
