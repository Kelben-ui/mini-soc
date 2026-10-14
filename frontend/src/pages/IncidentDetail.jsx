import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';
import { canCloseIncident } from '../api/auth';

const BLOCK_ACTIONS = ['block ip', 'block_ip', 'block-ip', 'block'];

function isBlockAction(actionType) {
  return BLOCK_ACTIONS.includes((actionType || '').trim().toLowerCase());
}

function statusClasses(status) {
  switch (status) {
    case 'executed':
      return 'bg-red-900 text-red-200';
    case 'unblocked':
      return 'bg-green-900 text-green-200';
    case 'failed':
      return 'bg-orange-900 text-orange-200';
    default:
      return 'bg-gray-700 text-gray-200';
  }
}

export default function IncidentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [incident, setIncident] = useState(null);
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('');
  const [actionType, setActionType] = useState('block ip');
  const [actionTarget, setActionTarget] = useState('');
  const [actionReason, setActionReason] = useState('');

  const fetchActions = async () => {
    try {
      const response = await client.get(`/api/incidents/${id}/actions`);
      setActions(Array.isArray(response.data) ? response.data : []);
    } catch {
      setError("Failed to load response actions.");
    }
  };

  useEffect(() => {
    const fetchIncident = async () => {
      try {
        const response = await client.get(`/api/incidents/${id}`);
        setIncident(response.data);
        setStatus(response.data.status);
      } catch {
        setError('Failed to load incident details.');
      } finally {
        setLoading(false);
      }
    };
    fetchIncident();
    fetchActions();
  }, [id]);

  const handleUpdateStatus = async (e) => {
    e.preventDefault();
    try {
      await client.patch(`/api/incidents/${id}/status`, { status, comment: "Status updated from dashboard" });
      alert('Incident status updated successfully!');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update the status.');
    }
  };

  // Recording just writes the intended action down; nothing is executed yet.
  const handleRecordAction = async (e) => {
    e.preventDefault();
    try {
      await client.post(`/api/incidents/${id}/actions`, {
        action_type: actionType,
        target: actionTarget,
        reason: actionReason || 'Recorded from the incident dashboard',
        result: 'Recorded for analyst review',
      });
      setActionTarget('');
      setActionReason('');
      await fetchActions();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not record the response action.');
    }
  };

  const handleExecute = async (action) => {
    const confirmed = window.confirm(
      `Block ${action.target}? This changes the firewall and is logged.`
    );
    if (!confirmed) return;
    try {
      const res = await client.post(`/api/actions/${action.id}/execute`, { confirm: true });
      alert(res.data.success ? `Blocked ${action.target}.` : `Block failed: ${res.data.message}`);
      await fetchActions();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error executing the response action.');
    }
  };

  const handleUnblock = async (action) => {
    const confirmed = window.confirm(`Remove the block on ${action.target}?`);
    if (!confirmed) return;
    try {
      const res = await client.post(`/api/actions/${action.id}/unblock`, { confirm: true });
      alert(res.data.success ? `Unblocked ${action.target}.` : `Unblock failed: ${res.data.message}`);
      await fetchActions();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error removing the block.');
    }
  };

  if (loading) return <div className="p-6 text-slate-300">Loading incident...</div>;
  if (error && !incident) return <div className="p-6 text-red-400">{error}</div>;
  if (!incident) return null;

  return (
    <div className="p-6 space-y-6 text-white max-w-4xl mx-auto">
      <button 
        onClick={() => navigate('/incidents')}
        className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
      >
        &larr; Back to Incidents
      </button>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow space-y-4">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold">{incident.title || `Incident #${incident.id || id}`}</h1>
            <p className="text-sm text-gray-400 font-mono mt-1">ID: {incident.id || id}</p>
          </div>
          <span className={`px-3 py-1 text-xs font-semibold uppercase rounded ${
            incident.severity === 'high' || incident.severity === 'critical' ? 'bg-red-900 text-red-200' : 'bg-yellow-900 text-yellow-200'
          }`}>
            {incident.severity}
          </span>
        </div>

        <div className="border-t border-gray-700 pt-4 space-y-2">
          <h3 className="text-sm font-semibold text-gray-400 uppercase">Description</h3>
          <p className="bg-gray-900 p-4 rounded text-gray-200">{incident.description || 'No description provided.'}</p>
        </div>

        <div className="border-t border-gray-700 pt-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase mb-1">Update Status</h3>
            {canCloseIncident() && (
            <form onSubmit={handleUpdateStatus} className="flex space-x-3">
              <select 
                value={status} 
                onChange={(e) => setStatus(e.target.value)}
                className="bg-gray-900 border border-gray-600 text-white text-sm rounded p-2"
              >
                <option value="open">Open</option>
                <option value="investigating">Investigating</option>
                <option value="contained">Contained</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
              <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-sm font-semibold rounded">
                Save
              </button>
            </form>
            )}
          </div>
        </div>
      </div>

      {canCloseIncident() && (
        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow space-y-4">
          <h3 className="text-sm font-semibold text-gray-400 uppercase">Response Actions</h3>

          <form onSubmit={handleRecordAction} className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Action</label>
              <select
                value={actionType}
                onChange={(e) => setActionType(e.target.value)}
                className="bg-gray-900 border border-gray-600 text-white text-sm rounded p-2"
              >
                <option value="block ip">Block IP</option>
                <option value="disable account">Disable account</option>
                <option value="isolate host">Isolate host</option>
                <option value="reset password">Reset password</option>
                <option value="patch">Patch</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Target</label>
              <input
                value={actionTarget}
                onChange={(e) => setActionTarget(e.target.value)}
                placeholder="203.0.113.5"
                required
                className="bg-gray-900 border border-gray-600 text-white text-sm rounded p-2"
              />
            </div>
            <div className="flex-1 min-w-[12rem]">
              <label className="block text-xs text-gray-400 mb-1">Reason</label>
              <input
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                placeholder="Confirmed malicious source"
                className="w-full bg-gray-900 border border-gray-600 text-white text-sm rounded p-2"
              />
            </div>
            <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-sm font-semibold rounded">
              Record
            </button>
          </form>

          {actions.length === 0 ? (
            <p className="text-sm text-gray-400">No response actions recorded yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="py-2">Action</th>
                  <th className="py-2">Target</th>
                  <th className="py-2">Status</th>
                  <th className="py-2">Result</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {actions.map((action) => (
                  <tr key={action.id} className="border-b border-gray-800 align-top">
                    <td className="py-2">{action.action_type}</td>
                    <td className="py-2 font-mono">{action.target}</td>
                    <td className="py-2">
                      <span className={`px-2 py-0.5 text-xs font-semibold uppercase rounded ${statusClasses(action.status)}`}>
                        {action.status}
                      </span>
                    </td>
                    <td className="py-2 text-gray-300">{action.result}</td>
                    <td className="py-2 space-x-2 whitespace-nowrap">
                      {isBlockAction(action.action_type) && action.status !== 'executed' && (
                        <button
                          onClick={() => handleExecute(action)}
                          className="px-3 py-1 bg-red-700 hover:bg-red-600 rounded text-xs font-semibold"
                        >
                          Execute Block
                        </button>
                      )}
                      {isBlockAction(action.action_type) && action.status === 'executed' && (
                        <button
                          onClick={() => handleUnblock(action)}
                          className="px-3 py-1 bg-gray-600 hover:bg-gray-500 rounded text-xs font-semibold"
                        >
                          Unblock
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
