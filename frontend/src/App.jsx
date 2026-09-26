import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';

function Login() { return <h1>Login</h1>; }
function Overview() { return <h1>Overview</h1>; }
function Alerts() { return <h1>Alerts List</h1>; }
function AlertDetail() { return <h1>Alert Detail</h1>; }
function Incidents() { return <h1>Incidents</h1>; }
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
        <Route path="/search" element={<EventSearch />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/reports" element={<Reports />} />
      </Routes>
    </BrowserRouter>
  );
}
