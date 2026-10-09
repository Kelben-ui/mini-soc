import { NavLink, useNavigate } from "react-router-dom";
import { logout, getRole } from "../api/auth";

const LINKS = [
  { to: "/", label: "Overview", end: true },
  { to: "/alerts", label: "Alerts" },
  { to: "/incidents", label: "Incidents" },
  { to: "/events", label: "Event Search" },
  { to: "/rules", label: "Rules" },
];

export default function NavBar() {
  const navigate = useNavigate();
  const role = getRole();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <nav className="nav">
      <div className="nav-brand">Mini SOC Platform</div>
      {LINKS.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          end={l.end}
          className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
        >
          {l.label}
        </NavLink>
      ))}
      <div className="nav-footer">
        {role && <div>Role: {role}</div>}
        <button className="secondary" style={{ marginTop: 8, width: "100%" }} onClick={handleLogout}>
          Log out
        </button>
      </div>
    </nav>
  );
}
