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
import ChainsList from "./pages/ChainsList";
import ChainDetail from "./pages/ChainDetail";
import EventSearch from "./pages/EventSearch";
import Rules from "./pages/Rules";
import Reports from "./pages/Reports";
import Users from "./pages/Users";

function Shell() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100 md:flex-row">
      <NavBar />
      <div className="flex min-w-0 flex-1 flex-col">
        <SeverityBanner />
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
          <Route path="/chains" element={<ChainsList />} />
          <Route path="/chains/:id" element={<ChainDetail />} />
          <Route path="/events" element={<EventSearch />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/users" element={<Users />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
