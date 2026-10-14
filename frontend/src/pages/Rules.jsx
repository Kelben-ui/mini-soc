import { useEffect, useState } from "react";
import { getRules } from "../api/rules";
import { severityClasses } from "../utils/severity";
import { tacticForTechnique } from "../constants/mitre";
import { formatDateTime } from "../utils/format";

export default function Rules() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    getRules()
      .then((res) => {
        if (cancelled) return;
        setRules(Array.isArray(res.data) ? res.data : res.data?.rules || []);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load detection rules.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p className="text-sm text-slate-400">Loading detection rules...</p>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Detection Rules</h1>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {rules.length === 0 ? (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
          No detection rules found.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-2">Rule</th>
                <th className="px-4 py-2">Severity</th>
                <th className="px-4 py-2">Category</th>
                <th className="px-4 py-2">MITRE</th>
                <th className="px-4 py-2">Tactic</th>
                <th className="px-4 py-2">Alerts</th>
                <th className="px-4 py-2">Last fired</th>
                <th className="px-4 py-2">Enabled</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {rules.map((rule) => (
                <tr key={rule.id} className="hover:bg-slate-900/60">
                  <td className="px-4 py-2">
                    <div className="font-semibold text-slate-100">{rule.name || rule.id}</div>
                    <div className="font-mono text-xs text-slate-500">{rule.id}</div>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${severityClasses(
                        rule.severity
                      )}`}
                    >
                      {rule.severity || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-2 capitalize text-slate-300">
                    {rule.category || "—"}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-300">
                    {rule.mitre || "—"}
                  </td>
                  <td className="px-4 py-2 text-slate-300">
                    {tacticForTechnique(rule.mitre)}
                  </td>
                  <td className="px-4 py-2 font-semibold text-slate-100">
                    {rule.alerts_count ?? 0}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-400">
                    {rule.last_fired ? formatDateTime(rule.last_fired) : "—"}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold ${
                        rule.enabled
                          ? "bg-emerald-950 text-emerald-300"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      {rule.enabled ? "enabled" : "disabled"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
