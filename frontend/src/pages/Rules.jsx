import { useEffect, useState } from "react";
import client from "../api/client";

export default function Rules() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    client
      .get("/api/rules")
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
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-center text-slate-500">
          No custom rules configured.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {rules.map((rule, index) => (
            <div
              key={rule.rule_id || rule.id || index}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900 p-4"
            >
              <div>
                <h3 className="text-lg font-semibold text-sky-300">
                  {rule.name || rule.title || rule.rule_id}
                </h3>
                <p className="mt-1 text-sm text-slate-400">
                  {rule.description || "No description"}
                </p>
              </div>
              <span
                className={`rounded px-3 py-1 text-xs font-bold uppercase ${
                  rule.enabled !== false
                    ? "bg-emerald-950 text-emerald-300"
                    : "bg-slate-800 text-slate-400"
                }`}
              >
                {rule.enabled !== false ? "Active" : "Disabled"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
