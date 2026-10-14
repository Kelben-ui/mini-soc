import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getChain, promoteChain } from "../api/chains";
import { groupAlertsByTactic } from "../constants/mitre";
import { severityClasses } from "../utils/severity";
import { formatDateTime } from "../utils/format";

export default function ChainDetail() {
  const { id } = useParams();

  const [chain, setChain] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    return getChain(id)
      .then((res) => {
        setChain(res.data);
        setError("");
      })
      .catch(() => setError("Could not load this attack chain."));
  }

  useEffect(() => {
    load();
  }, [id]);

  async function handlePromote() {
    if (
      !window.confirm(
        `Promote chain ${id} (${chain.alert_count} alerts) to one incident?`
      )
    ) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const res = await promoteChain(id);
      setNotice(`Incident ${res.data.incident_code} created.`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not promote the chain.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !chain) return <p className="text-sm text-red-400">{error}</p>;
  if (!chain) return <p className="text-sm text-slate-400">Loading chain...</p>;

  const phases = groupAlertsByTactic(chain.alerts || []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/chains" className="text-sm text-slate-400 hover:text-slate-200">
          ← Attack Chains
        </Link>
        <h1 className="text-2xl font-bold">Chain {chain.chain_id}</h1>
        <span
          className={`rounded px-2 py-0.5 text-xs font-semibold ${severityClasses(
            chain.max_severity
          )}`}
        >
          {chain.max_severity || "—"}
        </span>
      </div>

      {notice && (
        <p className="rounded border border-emerald-900 bg-emerald-950 px-3 py-2 text-sm text-emerald-300">
          {notice}
        </p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}

      <section className="grid grid-cols-2 gap-4 rounded-lg border border-slate-800 bg-slate-900 p-4 lg:grid-cols-4">
        <div>
          <div className="text-xs uppercase text-slate-500">Alerts</div>
          <div className="text-lg font-semibold">{chain.alert_count}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">First seen</div>
          <div className="text-sm">{formatDateTime(chain.first_seen)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Last seen</div>
          <div className="text-sm">{formatDateTime(chain.last_seen)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-500">Incident</div>
          {chain.promoted ? (
            <Link
              to={`/incidents/${chain.incident_id}`}
              className="text-sm text-sky-400 hover:underline"
            >
              #{chain.incident_id}
            </Link>
          ) : (
            <button
              type="button"
              onClick={handlePromote}
              disabled={busy}
              className="mt-1 rounded bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700 disabled:opacity-40"
            >
              Promote chain
            </button>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Kill-chain timeline
        </h2>

        <ol className="space-y-6">
          {phases.map((phase) => (
            <li key={phase.tactic}>
              <div className="mb-2 flex items-center gap-2">
                <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-sky-300">
                  {phase.tactic}
                </span>
                <span className="text-xs text-slate-500">
                  {phase.alerts.length} alert{phase.alerts.length === 1 ? "" : "s"}
                </span>
              </div>

              <ul className="space-y-2 border-l border-slate-800 pl-4">
                {phase.alerts.map((alert) => (
                  <li
                    key={alert.alert_id}
                    className="rounded border border-slate-800 bg-slate-950 p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/alerts/${alert.alert_id}`}
                        className="font-semibold text-sky-400 hover:underline"
                      >
                        {alert.title}
                      </Link>
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold ${severityClasses(
                          alert.severity
                        )}`}
                      >
                        {alert.severity}
                      </span>
                      {alert.mitre && (
                        <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
                          {alert.mitre}
                        </span>
                      )}
                      <span className="ml-auto text-xs text-slate-500">
                        {formatDateTime(alert.first_seen)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-400">
                      <span>Rule: {alert.rule_id}</span>
                      {alert.src_ip && <span className="font-mono">src {alert.src_ip}</span>}
                      {alert.dst_host && <span>host {alert.dst_host}</span>}
                      <span>status: {alert.status}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
