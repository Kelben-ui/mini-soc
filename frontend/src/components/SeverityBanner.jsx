export default function SeverityBanner({ alerts }) {
  const critical = alerts.find(
    (a) => ["HIGH", "CRITICAL"].includes(a.severity) && a.status === "NEW"
  );

  if (!critical) return null;

  return (
    <div className="banner-critical">
      {critical.severity} SEVERITY — {critical.title?.toUpperCase()}
    </div>
  );
}
