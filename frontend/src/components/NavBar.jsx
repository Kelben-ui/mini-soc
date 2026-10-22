import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { logout, getRole, isLead } from "../api/auth";

const LINKS = [
  { to: "/", label: "Overview", end: true },
  { to: "/alerts", label: "Alerts" },
  { to: "/incidents", label: "Incidents" },
  { to: "/chains", label: "Attack Chains" },
  { to: "/events", label: "Event Search" },
  { to: "/rules", label: "Rules" },
  { to: "/reports", label: "Reports" },
];

export default function NavBar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const role = getRole();

  // GET /api/users requires lead/admin, so only show the link they can use.
  const links = isLead()
    ? [...LINKS, { to: "/users", label: "Users" }]
    : LINKS;

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const linkClass = ({ isActive }) =>
    "block rounded px-3 py-2 text-sm font-medium transition " +
    (isActive
      ? "bg-slate-800 text-white"
      : "text-slate-300 hover:bg-slate-800/60 hover:text-white");

  return (
    <>
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900 px-4 py-3 md:hidden">
        <span className="font-semibold">SentinelX Platform</span>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="rounded border border-slate-700 px-3 py-1 text-sm hover:bg-slate-800"
          aria-expanded={open}
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>

      <nav
        className={
          (open ? "block" : "hidden") +
          " border-b border-slate-800 bg-slate-900 p-3 " +
          "md:flex md:w-60 md:flex-col md:border-b-0 md:border-r md:border-slate-800 md:p-4"
        }
      >
        <div className="mb-4 hidden md:block">
          <div className="text-lg font-bold">SentinelX</div>
          <div className="text-xs text-slate-400">Platform</div>
        </div>

        <div className="space-y-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={linkClass}
              onClick={() => setOpen(false)}
            >
              {link.label}
            </NavLink>
          ))}
        </div>

        <div className="mt-4 border-t border-slate-800 pt-3 md:mt-auto">
          <div className="mb-2 text-xs text-slate-400">
            Role: <span className="text-slate-200">{role}</span>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="w-full rounded bg-slate-800 px-3 py-2 text-sm font-medium hover:bg-slate-700"
          >
            Log out
          </button>
        </div>
      </nav>
    </>
  );
}
