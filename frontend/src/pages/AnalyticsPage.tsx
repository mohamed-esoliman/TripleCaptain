import React, { useEffect, useState } from 'react';
import apiClient from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

const AnalyticsPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [performance, setPerformance] = useState<any>(null);
  const [topPerformers, setTopPerformers] = useState<any[]>([]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const perf = await apiClient.getUserPerformance();
      setPerformance(perf);
      // naive: show top performers for GW1 for demo
      const res = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/v1/predictions/top-performers/1`);
      const tops = await res.json();
      setTopPerformers(Array.isArray(tops) ? tops : []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
          <h1 className="text-2xl font-bold text-gray-900">Performance Analytics</h1>
          <p className="mt-1 text-sm text-gray-500">Track your performance and analyze trends</p>
        </div>
        <div className="px-4 py-5 sm:p-6">
          {loading && <LoadingSpinner />}
          {error && <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>}
          {!loading && !error && (
            <div className="space-y-6">
              {performance && (
                <div className="bg-gray-50 rounded p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <div className="text-sm text-gray-500">Season</div>
                    <div className="text-xl font-medium text-gray-900">{performance.season}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500">Tracked Players</div>
                    <div className="text-xl font-medium text-gray-900">{performance.summary?.tracked_players ?? '-'}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500">Available Predictions</div>
                    <div className="text-xl font-medium text-gray-900">{performance.summary?.available_predictions ?? '-'}</div>
                  </div>
                </div>
              )}

              <div className="space-y-3">
                <h2 className="text-lg font-medium text-gray-900">Top Predicted Performers (GW1)</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {topPerformers.map((p: any) => (
                    <div key={p.player_id} className="border rounded p-3 bg-white">
                      <div className="text-sm font-medium text-gray-900">{p.player_name || p.web_name}</div>
                      <div className="text-xs text-gray-500">Team {p.team_id} • Pos {p.position}</div>
                      <div className="mt-2 text-sm">Predicted: <span className="font-medium">{p.predicted_points}</span> pts</div>
                      <div className="text-xs text-gray-500">Start Prob: {Math.round((p.start_probability || 0) * 100)}%</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AnalyticsPage;