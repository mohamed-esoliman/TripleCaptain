import React, { useMemo, useState } from 'react';
import apiClient from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import FormationPitch from '../components/common/FormationPitch';
import PlayerCard from '../components/common/PlayerCard';
import { OptimizationRequest, OptimizationResult, SquadPlayer } from '../types';

const defaultRequest: OptimizationRequest = {
  gameweek: 1,
  budget: 100.0,
  formation: '3-4-3',
  risk_tolerance: 0.5,
};

const SquadBuilder: React.FC = () => {
  const [request, setRequest] = useState<OptimizationRequest>(defaultRequest);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SquadPlayer | null>(null);
  const [importing, setImporting] = useState(false);
  const [entryId, setEntryId] = useState<string>('');

  const handleChange = (patch: Partial<OptimizationRequest>) => {
    setRequest((prev) => ({ ...prev, ...patch }));
  };

  const runOptimization = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiClient.optimizeSquad(request);
      setResult(res);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Optimization failed');
    } finally {
      setLoading(false);
    }
  };

  const quickPick = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.quickPick(request.gameweek, request.formation || '3-4-3', request.risk_tolerance || 0.5);
      setResult(res);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Quick pick failed');
    } finally {
      setLoading(false);
    }
  };

  // Wildcard: no import flow here.

  const starters = useMemo(() => result?.starting_xi || [], [result]);
  const bench = useMemo(() => result?.bench || [], [result]);

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
          <h1 className="text-2xl font-bold text-gray-900">Squad Builder</h1>
          <p className="mt-1 text-sm text-gray-500">Build and optimize your FPL squad using AI predictions</p>
        </div>

        {/* Controls */}
        <div className="px-4 py-4 sm:px-6 border-b border-gray-100">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
            <div>
              <label className="form-label">Gameweek</label>
              <input
                type="number"
                className="form-input mt-1"
                value={request.gameweek}
                onChange={(e) => handleChange({ gameweek: Number(e.target.value) })}
                min={1}
                max={38}
              />
            </div>
            <div>
              <label className="form-label">Budget (M)</label>
              <input
                type="number"
                step="0.1"
                className="form-input mt-1"
                value={request.budget}
                onChange={(e) => handleChange({ budget: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="form-label">Formation</label>
              <select
                className="form-input mt-1"
                value={request.formation}
                onChange={(e) => handleChange({ formation: e.target.value })}
              >
                {['3-4-3','3-5-2','4-3-3','4-4-2','4-5-1','5-3-2','5-4-1'].map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">Risk Tolerance</label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                className="w-full"
                value={request.risk_tolerance}
                onChange={(e) => handleChange({ risk_tolerance: Number(e.target.value) })}
              />
              <div className="text-xs text-gray-500">{request.risk_tolerance}</div>
            </div>
            <div className="flex gap-2">
              <button className="btn-secondary w-full" onClick={quickPick} disabled={loading}>
                {loading ? 'Picking…' : 'Quick Pick'}
              </button>
              <button className="btn-primary w-full" onClick={runOptimization} disabled={loading}>
                {loading ? 'Optimizing…' : 'Optimize Squad'}
              </button>
            </div>
          </div>
        </div>

        <div className="px-4 py-5 sm:p-6">
          {loading && <LoadingSpinner />}
          {error && <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>}
          {!loading && !error && result && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-4">
                  <h2 className="text-lg font-medium text-gray-900">Starting XI ({result.formation})</h2>
                  <FormationPitch starters={starters} formation={result.formation} selectedId={selected?.player_id} onSelect={setSelected} />
                </div>
                <div className="space-y-4">
                  <h2 className="text-lg font-medium text-gray-900">Bench</h2>
                  <div className="space-y-2">
                    {bench.map((p) => (
                      <div key={p.player_id} onClick={() => setSelected(p)}>
                        <PlayerCard player={{
                          player_id: p.player_id,
                          position: p.position,
                          team_id: p.team_id,
                          current_price: p.price,
                          predicted_points: p.predicted_points,
                          name: p.name,
                        }} compact highlight={selected?.player_id === p.player_id} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Total Cost</div>
                  <div className="text-xl font-medium text-gray-900">£{result.total_cost.toFixed(1)}M</div>
                </div>
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Predicted Points</div>
                  <div className="text-xl font-medium text-gray-900">{result.predicted_points.toFixed(1)}</div>
                </div>
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Captain</div>
                  <div className="text-xl font-medium text-gray-900">#{result.captain_id}</div>
                </div>
              </div>
            </div>
          )}
          {!loading && !error && !result && (
            <div className="text-sm text-gray-500">Set your constraints and click Optimize Squad.</div>
          )}
        </div>
      </div>
      {selected && (
        <div className="fixed inset-0 z-30">
          <div className="absolute inset-0 bg-black/30" onClick={() => setSelected(null)} />
          <div className="absolute right-0 top-0 h-full w-full sm:w-[28rem] bg-white shadow-xl p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-medium text-gray-900">Selected Player</h3>
              <button className="text-gray-500 hover:text-gray-700" onClick={() => setSelected(null)}>✕</button>
            </div>
            <PlayerCard
              player={{
                player_id: selected.player_id,
                position: selected.position,
                team_id: selected.team_id,
                current_price: selected.price,
                predicted_points: selected.predicted_points,
                name: selected.name,
                is_captain: selected.is_captain,
              }}
            />
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded bg-gray-50 p-3">
                <div className="text-xs text-gray-500">Predicted Points</div>
                <div className="text-base font-medium">{selected.predicted_points.toFixed?.(1) ?? selected.predicted_points}</div>
              </div>
              <div className="rounded bg-gray-50 p-3">
                <div className="text-xs text-gray-500">Price</div>
                <div className="text-base font-medium">£{Number(selected.price).toFixed(1)}M</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SquadBuilder;