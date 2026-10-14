import { useEffect, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
} from "react-router-dom";

import ProtectedRoute from "./components/ProtectedRoute";
import NavBar from "./components/NavBar";
import SeverityBanner from "./components/SeverityBanner";

import Login from "./pages/Login";
import Overview from "./pages/Overview";
import AlertsList from "./pages/AlertsList";
import AlertDetail from "./pages/AlertDetail";
import IncidentsList from "./pages/IncidentsList";
import IncidentDetail from "./pages/IncidentDetail";
import EventSearch from "./pages/EventSearch";
import Rules from "./pages/Rules";

import { getAlerts } from "./api/alerts";
import { isLoggedIn } from "./api/auth";

function Shell() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    if (!isLoggedIn()) return;

    let cancelled = false;

    function fetchAlerts() {
      getAlerts({ limit: 100 })
        .then((res) => {
          if (cancelled) return;
          setAlerts(res.data?.items || []);
        })
        .catch(() => {});
    }

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 8000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100 md:flex-row">
      <NavBar />
      <div className="flex min-w-0 flex-1 flex-col">
        <SeverityBanner alerts={alerts} />
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Shell />
            </ProtectedRoute>
          }
        >
          <Route index element={<Overview />} />
          <Route path="/alerts" element={<AlertsList />} />
          <Route path="/alerts/:id" element={<AlertDetail />} />
          <Route path="/incidents" element={<IncidentsList />} />
          <Route path="/incidents/:id" element={<IncidentDetail />} />
          <Route path="/events" element={<EventSearch />} />
          <Route path="/rules" element={<Rules />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
