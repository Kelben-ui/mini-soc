import React, { useState, useEffect } from 'react';
import client from '../api/client'; // Adjust path to your client.js if needed

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await client.get('/api/stats');
        setStats(response.data);
      } catch (err) {
        console.error('Failed to fetch SOC stats:', err);
        setError('Failed to load dashboard metrics.');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) return <div className="p-6 text-white">Loading SOC overview...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;
  if (!stats) return null;

  return (
    <div className="p-6 space-y-6 text-white">
      <h1 className="text-2xl font-bold tracking-wide">SOC Dashboard Overview</h1>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800 p-5 rounded-lg border border-gray-700 shadow">
          <h3 className="text-sm font-medium text-gray-400 uppercase">Total Events</h3>
          <p className="text-3xl font-extrabold mt-2 text-blue-400">{stats.total_events}</p>
        </div>

        <div className="bg-gray-800 p-5 rounded-lg border border-gray-700 shadow">
          <h3 className="text-sm font-medium text-gray-400 uppercase">Total Alerts</h3>
          <p className="text-3xl font-extrabold mt-2 text-yellow-400">{stats.total_alerts}</p>
        </div>

        <div className="bg-gray-800 p-5 rounded-lg border border-gray-700 shadow">
          <h3 className="text-sm font-medium text-gray-400 uppercase">Total Incidents</h3>
          <p className="text-3xl font-extrabold mt-2 text-red-400">{stats.total_incidents}</p>
        </div>
      </div>

      {/* Agent + IDS health (task 3.7) */}
      <div className="bg-gray-800 p-5 rounded-lg border border-gray-700 shadow space-y-4">
        <h2 className="text-lg font-semibold text-gray-200 border-b border-gray-700 pb-2">
          Agent &amp; IDS Health
        </h2>

        <div className="flex flex-wrap gap-4">
          <span
            className={`px-3 py-1 rounded text-sm font-semibold ${
              stats.ids_status === 'active'
                ? 'bg-green-900 text-green-300'
                : 'bg-red-900 text-red-300'
            }`}
          >
            IDS: {stats.ids_status || 'unknown'}
          </span>

          <span className="px-3 py-1 rounded text-sm font-semibold bg-gray-900 text-gray-300">
            Agents online: {stats.agents_online ?? 0} / {(stats.agents || []).length}
          </span>
        </div>

        {(stats.agents || []).length === 0 ? (
          <p className="text-sm text-gray-400">No agent has reported a heartbeat yet.</p>
        ) : (
          <ul className="space-y-1">
            {stats.agents.map((agent) => (
              <li
                key={agent.name}
                className="flex justify-between text-sm bg-gray-900 p-2 rounded"
              >
                <span>
                  <span className={agent.status === 'online' ? 'text-green-400' : 'text-red-400'}>
                    ●
                  </span>{' '}
                  {agent.name}
                  {agent.host ? ` (${agent.host})` : ''}
                </span>
                <span className="text-gray-400">
                  IDS: {agent.ids_status || 'n/a'}
                  {agent.last_heartbeat
                    ? ` · ${new Date(agent.last_heartbeat).toLocaleTimeString()}`
                    : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Detailed Breakdown Grids */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Alerts Breakdown */}
        <div className="bg-gray-800 p-5 rounded-lg border border-gray-700 shadow space-y-4">
          <h2 className="text-lg font-semibold text-gray-200 border-b border-gray-700 pb-2">Alerts Breakdown</h2>
          
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">By Severity</h4>
            <ul className="space-y-1">
              {Object.entries(stats.alerts_by_severity || {}).map(([severity, count]) => (
                <li key={severity} className="flex justify-between text-sm bg-gray-900 p-2 rounded">
                  <span className="capitalize">{severity}</span>
                  <span className="font-bold text-gray-300">{count}</span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">By Status</h4>
            <ul className="space-y-1">
              {Object.entries(stats.alerts_by_status || {}).map(([status, count]) => (
                <li key={status} className="flex justify-between text-sm bg-gray-900 p-2 rounded">
                  <span className="capitalize">{status}</span>
                  <span className="font-bold text-gray-300">{count}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Incidents Breakdown */}
        <div className="bg-gray-800 p-5 rounded-lg border border-gray-700 shadow space-y-4">
          <h2 className="text-lg font-semibold text-gray-200 border-b border-gray-700 pb-2">Incidents Breakdown</h2>
          
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">By Severity</h4>
            <ul className="space-y-1">
              {Object.entries(stats.incidents_by_severity || {}).map(([severity, count]) => (
                <li key={severity} className="flex justify-between text-sm bg-gray-900 p-2 rounded">
                  <span className="capitalize">{severity}</span>
                  <span className="font-bold text-gray-300">{count}</span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">By Status</h4>
            <ul className="space-y-1">
              {Object.entries(stats.incidents_by_status || {}).map(([status, count]) => (
                <li key={status} className="flex justify-between text-sm bg-gray-900 p-2 rounded">
                  <span className="capitalize">{status}</span>
                  <span className="font-bold text-gray-300">{count}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
