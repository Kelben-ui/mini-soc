import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useParams } from 'react-router-dom';
import { PLAYBOOK_MAP } from './playbookMap';
import SeverityBanner from './components/SeverityBanner';

import Login from "./pages/Login";
function Overview() { return <h1>Overview</h1>; }
function Alerts() { return <h1>Alerts List</h1>; }

function AlertDetail() {
  const { id } = useParams();
  const mockAlert = { alert_id: id, rule_id: "SSH-BF-001", title: "SSH brute force", severity: "HIGH" };

  const [playbookText, setPlaybookText] = useState(null);

  useEffect(() => {
    const filename = PLAYBOOK_MAP[mockAlert.rule_id];
    if (!filename) { setPlaybookText("No playbook mapped for this rule."); return; }
    fetch(`/playbooks/${filename}`)
      .then(res => res.text())
      .then(setPlaybookText)
      .catch(() => setPlaybookText("Could not load playbook."));
  }, [mockAlert.rule_id]);

  return (
    <div>
      <SeverityBanner severity={mockAlert.severity} title={mockAlert.title} />
      <h1>Alert Detail: {mockAlert.title}</h1>
      <p>Rule: {mockAlert.rule_id} | Severity: {mockAlert.severity}</p>
      <hr />
      <h2>Response Playbook</h2>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{playbookText}</pre>
    </div>
  );
}

function Incidents() { return <h1>Incidents</h1>; }
function IncidentDetail() { return <h1>Incident Detail</h1>; }
function EventSearch() { return <h1>Event Search</h1>; }
function Rules() { return <h1>Rules</h1>; }
function Reports() { return <h1>Reports</h1>; }

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <Link to="/">Overview</Link> | <Link to="/alerts">Alerts</Link> |{' '}
        <Link to="/incidents">Incidents</Link> | <Link to="/search">Search</Link> |{' '}
        <Link to="/rules">Rules</Link> | <Link to="/reports">Reports</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/login" element={<Login />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/alerts/:id" element={<AlertDetail />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/incidents/:id" element={<IncidentDetail />} />
        <Route path="/search" element={<EventSearch />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/reports" element={<Reports />} />
      </Routes>
    </BrowserRouter>
  );
}
