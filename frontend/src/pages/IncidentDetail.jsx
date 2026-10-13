import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import client from '../api/client';
import { canCloseIncident } from '../api/auth';
export default function IncidentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const fetchIncident = async () => {
      try {
        const response = await client.get(`/api/incidents/${id}`);
        setIncident(response.data);
        setStatus(response.data.status);
      } catch (err) {
        console.error('Failed to fetch incident details:', err);
        setError('Failed to load incident details.');
      } finally {
        setLoading(false);
      }
    };
    fetchIncident();
  }, [id]);

  const handleUpdateStatus = async (e) => {
    e.preventDefault();
    try {
      await client.patch(`/api/incidents/${id}/status`, { status, comment: "Status updated from dashboard" });
      alert('Incident status updated successfully!');
    } catch (err) {
      console.error('Failed to update status:', err);
      alert('Error updating status.');
    }
  };

  if (loading) return <div className="p-6 text-white">Loading incident...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;
  if (!incident) return null;

  return (
    <div className="p-6 space-y-6 text-white max-w-4xl mx-auto">
      <button 
        onClick={() => navigate('/incidents')}
        className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
      >
        &larr; Back to Incidents
      </button>

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
    </div>
  );
}
