import React, { useState } from 'react';
import client from '../api/client';

export default function EventSearch() {
  const [query, setQuery] = useState('');
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await client.get(`/api/events?q=${encodeURIComponent(query)}`);
      setEvents(Array.isArray(response.data) ? response.data : response.data.events || []);
    } catch (err) {
      console.error('Failed to search events:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 text-white max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold">Event & Log Search</h1>

      <form onSubmit={handleSearch} className="flex gap-4">
        <input 
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search logs by IP, message, or keyword..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded p-3 text-white text-sm focus:ring-blue-500"
        />
        <button type="submit" className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded font-semibold text-sm">
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden shadow">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-900 text-gray-400 text-xs uppercase tracking-wider border-b border-gray-700">
              <th className="p-4">Timestamp</th>
              <th className="p-4">Source</th>
              <th className="p-4">Payload / Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700 text-sm font-mono">
            {events.length === 0 ? (
              <tr>
                <td colSpan="3" className="p-6 text-center text-gray-400 font-sans">
                  No events found. Enter a query or clear filters to view logs.
                </td>
              </tr>
            ) : (
              events.map((ev, index) => (
                <tr key={ev.id || index} className="hover:bg-gray-750">
                  <td className="p-4 text-xs text-gray-400">{ev.timestamp || 'N/A'}</td>
                  <td className="p-4 text-blue-400">{ev.source || 'Unknown'}</td>
                  <td className="p-4 text-xs text-gray-300 break-all">
                    {JSON.stringify(ev.payload || ev)}
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
