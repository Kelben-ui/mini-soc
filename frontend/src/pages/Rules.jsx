import React, { useState, useEffect } from 'react';
import client from '../api/client';

export default function Rules() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRules = async () => {
      try {
        const response = await client.get('/api/rules');
        setRules(Array.isArray(response.data) ? response.data : response.data.rules || []);
      } catch (err) {
        console.error('Failed to fetch rules:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchRules();
  }, []);

  if (loading) return <div className="p-6 text-white">Loading detection rules...</div>;

  return (
    <div className="p-6 space-y-6 text-white max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold">Detection Rules Configuration</h1>

      <div className="grid grid-cols-1 gap-4">
        {rules.length === 0 ? (
          <div className="bg-gray-800 p-6 rounded border border-gray-700 text-gray-400 text-center">
            No custom rules configured.
          </div>
        ) : (
          rules.map((rule) => (
            <div key={rule.id || rule.rule_id} className="bg-gray-800 p-5 rounded-lg border border-gray-700 flex justify-between items-center shadow">
              <div>
                <h3 className="font-semibold text-lg text-blue-400">{rule.name || rule.title}</h3>
                <p className="text-sm text-gray-400 mt-1">{rule.description || 'No description'}</p>
              </div>
              <span className={`px-3 py-1 rounded text-xs font-bold uppercase ${
                rule.enabled !== false ? 'bg-green-900 text-green-200' : 'bg-gray-700 text-gray-400'
              }`}>
                {rule.enabled !== false ? 'Active' : 'Disabled'}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
