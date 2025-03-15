import React, { useCallback, useEffect, useState } from 'react';
import api from '../services/api';

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="rounded-lg bg-white p-4 shadow">
    <h2 className="mb-3 text-lg font-semibold text-gray-800">{title}</h2>
    {children}
  </div>
);

const AdminPage: React.FC = () => {
  const [health, setHealth] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [cacheStats, setCacheStats] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>('');
  const [gameweek, setGameweek] = useState<number>(1);
  const [pattern, setPattern] = useState<string>('*');

  const loadOverview = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([api.getAdminHealth(), api.getSystemStats()]);
      setHealth(h);
      setStats(s);
    } catch (e: any) {
      // ignore errors in overview
    }
  }, []);

  const loadCache = useCallback(async () => {
    try {
      const cs = await api.getAdminCacheStats();
      setCacheStats(cs);
    } catch (e: any) {
      // ignore errors
    }
  }, []);

  useEffect(() => {
    loadOverview();
    loadCache();
  }, [loadOverview, loadCache]);

  const runTask = async (task: 'data_sync' | 'generate_predictions' | 'train_models' | 'clear_cache') => {
    setLoading(true);
    setMessage('');
    try {
      const params: any = {};
      if (task === 'generate_predictions') params.gameweek = gameweek;
      if (task === 'clear_cache') params.pattern = pattern;
      const res = await api.runAdminTask(task, params);
      setMessage(JSON.stringify(res));
      if (task === 'clear_cache') await loadCache();
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Admin</h1>

      <Section title="Overview">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded border p-3">
            <div className="mb-2 text-sm font-medium text-gray-600">Health</div>
            <pre className="whitespace-pre-wrap break-words text-xs text-gray-800">{health ? JSON.stringify(health, null, 2) : '—'}</pre>
          </div>
          <div className="rounded border p-3">
            <div className="mb-2 text-sm font-medium text-gray-600">System Stats</div>
            <pre className="whitespace-pre-wrap break-words text-xs text-gray-800">{stats ? JSON.stringify(stats, null, 2) : '—'}</pre>
          </div>
        </div>
      </Section>

      <Section title="Model & Data Maintenance">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded border p-3">
            <div className="mb-2 text-sm font-medium text-gray-600">Train Models</div>
            <button
              onClick={() => runTask('train_models')}
              disabled={loading}
              className="rounded bg-fpl-green px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-60"
            >
              {loading ? 'Running…' : 'Trigger Training'}
            </button>
          </div>
          <div className="rounded border p-3">
            <div className="mb-2 text-sm font-medium text-gray-600">Generate Predictions</div>
            <div className="mb-2 flex items-center space-x-2">
              <label className="text-sm text-gray-600" htmlFor="gw">GW</label>
              <input
                id="gw"
                type="number"
                min={1}
                max={38}
                value={gameweek}
                onChange={(e) => setGameweek(parseInt(e.target.value || '1', 10))}
                className="w-24 rounded border px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={() => runTask('generate_predictions')}
              disabled={loading}
              className="rounded bg-fpl-green px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-60"
            >
              {loading ? 'Running…' : 'Generate'}
            </button>
          </div>
          <div className="rounded border p-3">
            <div className="mb-2 text-sm font-medium text-gray-600">Full Data Sync</div>
            <button
              onClick={() => runTask('data_sync')}
              disabled={loading}
              className="rounded bg-fpl-green px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-60"
            >
              {loading ? 'Running…' : 'Sync Now'}
            </button>
          </div>
        </div>
      </Section>

      <Section title="Cache Management">
        <div className="mb-3 flex items-center space-x-2">
          <label className="text-sm text-gray-600" htmlFor="pattern">Pattern</label>
          <input
            id="pattern"
            type="text"
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            className="w-64 rounded border px-2 py-1 text-sm"
            placeholder="e.g., players:*"
          />
          <button
            onClick={() => runTask('clear_cache')}
            disabled={loading}
            className="rounded bg-red-600 px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-60"
          >
            {loading ? 'Clearing…' : 'Clear Cache'}
          </button>
        </div>
        <div className="rounded border p-3">
          <div className="mb-2 text-sm font-medium text-gray-600">Cache Stats</div>
          <pre className="whitespace-pre-wrap break-words text-xs text-gray-800">{cacheStats ? JSON.stringify(cacheStats, null, 2) : '—'}</pre>
        </div>
      </Section>

      {message && (
        <div className="rounded bg-blue-50 p-3 text-sm text-blue-800">
          <div className="font-medium">Result</div>
          <pre className="whitespace-pre-wrap break-words">{message}</pre>
        </div>
      )}
    </div>
  );
};

export default AdminPage;


