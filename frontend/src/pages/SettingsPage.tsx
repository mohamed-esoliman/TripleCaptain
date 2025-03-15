import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../services/api';

const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const [username, setUsername] = useState<string>(user?.username || '');
  const [teamId, setTeamId] = useState<string>(user?.fpl_team_id ? String(user.fpl_team_id) : '');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      await apiClient.updateCurrentUser({ username, fpl_team_id: teamId ? Number(teamId) : undefined });
      setMessage('Settings saved');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="mt-1 text-sm text-gray-500">Update your profile and link your FPL team</p>
        </div>
        <div className="px-4 py-5 sm:p-6 space-y-4">
          {message && <div className="rounded bg-green-50 text-green-800 text-sm p-3">{message}</div>}
          {error && <div className="rounded bg-red-50 text-red-700 text-sm p-3">{error}</div>}
          <div>
            <label className="form-label">Username</label>
            <input className="form-input mt-1" value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label className="form-label">FPL Team ID (entry)</label>
            <input className="form-input mt-1" value={teamId} onChange={(e) => setTeamId(e.target.value)} placeholder="e.g. 1234567" />
            <div className="text-xs text-gray-500 mt-1">Used to fetch your team and points from FPL.</div>
          </div>
          <div>
            <button className="btn-primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save Settings'}</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;


