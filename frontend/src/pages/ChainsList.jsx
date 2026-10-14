import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getChains, promoteChain } from "../api/chains";
import { severityClasses } from "../utils/severity";
import { formatDateTime } from "../utils/format";

const POLL_MS = 10000;

export default function ChainsList() {
  const [chains, setChains] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState(null);

  function load() {
    return getChains()
      .then((res) => {
        setChains(res.data?.items || []);
        setError("");
      })
      .catch(() => setError("Could not load attack chains."));
  }

  useEffect(() => {
    let cancelled = false;

    function fetchChains() {
      getChains()
        .then((res) => {
          if (cancelled) return;
          setChains(res.data?.items || []);
          setError("");
        })
        .catch(() => {
          if (!cancelled) setError("Could not load attack chains.");
        });
    }

    fetchChains();
    const interval = setInterval(fetchChains, POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  async function handlePromote(chain) {
    if (
      !window.confirm(
        `Promote attack chain ${chain.chain_id} (${chain.alert_count} alerts) to an incident?`
      )
    ) {
      return;
    }

    setBusyId(chain.chain_id);
    setError("");
    setNotice("");

    try {
      const res = await promoteChain(chain.chain_id);
      setNotice(`Incident ${res.data.incident_code} created from chain ${chain.chain_id}.`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not promote the chain.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Attack Chains</h1>
      <p className="text-sm text-slate-400">
        Alerts correlated by the detection engine (same source within 30 minutes
        across categories). Promote a chain to investigate it as one incident.
      </p>

      {notice && (
        <p className="rounded border border-emerald-900 bg-emerald-950 px-3 py-2 text-sm text-emerald-300">
          {notice}
        </p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full min-w-[56rem] text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Chain</th>
              <th className="px-4 py-3">Alerts</th>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Categories</th>
              <th className="px-4 py-3">Source IPs</th>
              <th className="px-4 py-3">Last seen</th>
              <th className="px-4 py-3">Incident</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {chains.length === 0 ? (
              <tr>
                <td colSpan="7" className="px-4 py-8 text-center text-slate-500">
                  No correlated attack chains yet.
                </td>
              </tr>
            ) : (
              chains.map((chain) => (
                <tr key={chain.chain_id} className="hover:bg-slate-900/60">
                  <td className="px-4 py-3">
                    <Link
                      to={`/chains/${chain.chain_id}`}
                      className="text-sky-400 hover:underline"
                    >
                      Chain {chain.chain_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{chain.alert_count}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold ${severityClasses(
                        chain.max_severity
                      )}`}
                    >
                      {chain.max_severity || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 capitalize text-slate-300">
                    {(chain.categories || []).join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {(chain.src_ips || []).join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {formatDateTime(chain.last_seen)}
                  </td>
                  <td className="px-4 py-3">
                    {chain.promoted ? (
                      <Link
                        to={`/incidents/${chain.incident_id}`}
                        className="text-sky-400 hover:underline"
                      >
                        #{chain.incident_id}
                      </Link>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handlePromote(chain)}
                        disabled={busyId === chain.chain_id}
                        className="rounded bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700 disabled:opacity-40"
                      >
                        Promote
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
