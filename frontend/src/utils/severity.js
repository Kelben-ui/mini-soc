export const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

const SEVERITY_RANK = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

export function severityClasses(severity) {
  switch ((severity || "").toUpperCase()) {
    case "CRITICAL":
      return "bg-red-950 text-red-300 border border-red-900";
    case "HIGH":
      return "bg-orange-950 text-orange-300 border border-orange-900";
    case "MEDIUM":
      return "bg-amber-950 text-amber-300 border border-amber-900";
    case "LOW":
      return "bg-sky-950 text-sky-300 border border-sky-900";
    default:
      return "bg-slate-800 text-slate-300 border border-slate-700";
  }
}

export function statusClasses(status) {
  switch ((status || "").toUpperCase()) {
    case "NEW":
      return "bg-slate-800 text-slate-200";
    case "INVESTIGATING":
      return "bg-sky-950 text-sky-300";
    case "CONTAINED":
      return "bg-emerald-950 text-emerald-300";
    case "RESOLVED":
      return "bg-slate-700 text-slate-200";
    case "FALSE POSITIVE":
      return "bg-slate-800 text-slate-400";
    default:
      return "bg-slate-800 text-slate-300";
  }
}

export function severityRank(severity) {
  return SEVERITY_RANK[(severity || "").toUpperCase()] || 0;
}

export function threatLevelClasses(level) {
  switch ((level || "").toUpperCase()) {
    case "CRITICAL":
      return "border-red-800 bg-red-950 text-red-100";
    case "HIGH":
      return "border-orange-800 bg-orange-950 text-orange-100";
    case "MEDIUM":
      return "border-amber-800 bg-amber-950 text-amber-100";
    default:
      return "border-sky-800 bg-sky-950 text-sky-100";
  }
}
