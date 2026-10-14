import { Link } from "react-router-dom";

export default function SeverityBanner({ alerts }) {
  const critical = alerts.find(
    (alert) =>
      ["HIGH", "CRITICAL"].includes(alert.severity) && alert.status === "NEW"
  );

  if (!critical) return null;

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-red-800 bg-red-950 px-4 py-2 text-sm text-red-100">
      <span className="font-semibold">
        {critical.severity} SEVERITY — {critical.title?.toUpperCase()}
      </span>
      <Link
        to={`/alerts/${critical.alert_id}`}
        className="rounded bg-red-800 px-2 py-0.5 text-xs font-semibold hover:bg-red-700"
      >
        Investigate
      </Link>
    </div>
  );
}
