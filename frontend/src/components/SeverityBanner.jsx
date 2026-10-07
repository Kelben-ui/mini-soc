export default function SeverityBanner({ severity, title }) {
  if (severity !== "HIGH" && severity !== "CRITICAL") return null;
  return (
    <div style={{
      background: severity === "CRITICAL" ? "#7a0000" : "#b30000",
      color: "white", padding: "10px", fontWeight: "bold", textAlign: "center"
    }}>
      {severity} SEVERITY — {title.toUpperCase()}
    </div>
  );
}
