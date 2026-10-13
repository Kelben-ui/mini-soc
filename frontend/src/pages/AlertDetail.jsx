import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { getAlert } from "../api/alerts";
import { PLAYBOOK_MAP } from "../playbookMap";


export default function AlertDetail() {
  const { id } = useParams();
  const [alert, setAlert] = useState(null);
  const [error, setError] = useState("");
  const [playbookText, setPlaybookText] = useState(null);

  useEffect(() => {
    getAlert(id)
      .then((res) => setAlert(res.data))
      .catch(() => setError("Could not load this alert."));
  }, [id]);

  useEffect(() => {
    if (!alert) return;
    const filename = PLAYBOOK_MAP[alert.rule_id];
    if (!filename) {
      setPlaybookText("No playbook mapped for this rule.");
      return;
    }
    fetch(`/playbooks/${filename}`)
      .then((res) => res.text())
      .then(setPlaybookText)
      .catch(() => setPlaybookText("Could not load playbook."));
  }, [alert]);

  if (error) return <p className="error-text">{error}</p>;
  if (!alert) return <p className="muted">Loading...</p>;

  return (
    <div>
      <h1 className="page-title">Alert Detail: {alert.title}</h1>
      <div className="card">
        <p><strong>Rule:</strong> {alert.rule_id}</p>
        <p><strong>Severity:</strong> {alert.severity}</p>
        <p><strong>Status:</strong> {alert.status}</p>
        <p><strong>Source IP:</strong> {alert.src_ip}</p>
        <p><strong>First seen:</strong> {alert.first_seen}</p>
        <p><strong>Last seen:</strong> {alert.last_seen}</p>
      </div>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Response Playbook</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{playbookText}</pre>
      </div>
    </div>
  );
}
