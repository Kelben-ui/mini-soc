import React, { useState, useEffect } from 'react';
import client from '../api/client';

export default function IncidentsList() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);

  // Fetch incidents list on mount
  const fetchIncidents = async () => {
    try {
      setLoading(true);
      const response = await client.get('/api/incidents');
      // Adjust based on whether your response is an array or an object containing an array (e.g. response.data.items)
      setIncidents(Array.isArray(response.data) ? response.data : response.data.incidents || []);
    } catch (err) {
      console.error('Failed to fetch incidents:', err);
      setError('Failed to load incidents list.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  // Handle status update via PATCH endpoint
  const handleStatusChange = async (incidentId, newStatus) => {
    try {
      setUpdatingId(incidentId);
      await client.patch(`/api/incidents/${incidentId}/status`, {
  status: newStatus,
  comment: "Status updated from incidents list"
});
      
      // Refresh the incidents list locally or re-fetch
      setIncidents(prev => 
        prev.map(inc => 
          (inc.id === incidentId || inc.incident_id === incidentId) 
            ? { ...inc, status: newStatus } 
            : inc
        )
      );
    } catch (err) {
      console.error('Failed to update incident status:', err);
      alert('Error updating status. Please try again.');
    } finally {
      setUpdatingId(null);
    }
  };

  if (loading) return <div className="p-6 text-white">Loading incidents...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;

  return (
    <div className="p-6 space-y-6 text-white">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold tracking-wide">Security Incidents</h1>
        <button 
          onClick={fetchIncidents}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-sm font-semibold rounded transition"
        >
          Refresh List
        </button>
      </div>

      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden shadow">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-900 text-gray-400 text-xs uppercase tracking-wider border-b border-gray-700">
              <th className="p-4">ID</th>
              <th className="p-4">Severity</th>
              <th className="p-4">Description / Title</th>
              <th className="p-4">Current Status</th>
              <th className="p-4">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700 text-sm">
            {incidents.length === 0 ? (
              <tr>
                <td colSpan="5" className="p-6 text-center text-gray-400">
                  No incidents recorded.
                </td>
              </tr>
            ) : (
              incidents.map((incident) => {
                const id = incident.id || incident.incident_id;
                return (
                  <tr key={id} className="hover:bg-gray-750 transition">
                    <td className="p-4 font-mono text-xs text-gray-400">{id}</td>
                    <td className="p-4">
                      <span className={`px-2 py-1 text-xs font-semibold rounded uppercase ${
                        incident.severity === 'high' || incident.severity === 'critical' 
                          ? 'bg-red-900 text-red-200' 
                          : 'bg-yellow-900 text-yellow-200'
                      }`}>
                        {incident.severity}
                      </span>
                    </td>
                    <td className="p-4 font-medium">{incident.title || incident.description || 'N/A'}</td>
                    <td className="p-4">
                      <span className="capitalize px-2 py-1 bg-gray-900 rounded text-gray-300">
                        {incident.status}
                      </span>
                    </td>
                    <td className="p-4">
                      <select 
                        value={incident.status}
                        disabled={updatingId === id}
                        onChange={(e) => handleStatusChange(id, e.target.value)}
                        className="bg-gray-900 border border-gray-600 text-white text-xs rounded p-2 focus:ring-blue-500 focus:border-blue-500"
                      >
                        <option value="open">Open</option>
                        <option value="investigating">Investigating</option>
                        <option value="resolved">Resolved</option>
                        <option value="closed">Closed</option>
                      </select>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
