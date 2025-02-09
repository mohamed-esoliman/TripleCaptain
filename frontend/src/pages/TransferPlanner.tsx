import React, { useEffect, useState } from 'react';
import apiClient from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { GameweekPlan, TransferOption, TransferPlanRequest, TransferPlanResult } from '../types';

const TransferPlanner: React.FC = () => {
  const [currentSquad, setCurrentSquad] = useState<string>('');
  const [planningHorizon, setPlanningHorizon] = useState<number>(5);
  const [maxTransfersPerWeek, setMaxTransfersPerWeek] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<TransferPlanResult | null>(null);

  // Prefill with current saved squad if available
  useEffect(() => {
    const prefill = async () => {
      try {
        const cur = await apiClient.getCurrentSquad();
        const ids: number[] = [
          ...(cur?.squad?.starting_xi?.map((p: any) => p.player_id) || []),
          ...(cur?.squad?.bench?.map((p: any) => p.player_id) || []),
        ];
        if (ids.length) {
          setCurrentSquad(ids.join(', '));
        } else {
          // fallback to FPL import if user has team linked
          try {
            const team = await apiClient.getTeamSummary();
            const tids = [
              ...(team?.squad?.starting_xi?.map((p: any) => p.player_id) || []),
              ...(team?.squad?.bench?.map((p: any) => p.player_id) || []),
            ];
            if (tids.length) setCurrentSquad(tids.join(', '));
          } catch {}
        }
      } catch {}
    };
    prefill();
  }, []);

  const parseSquadIds = (): number[] =>
    currentSquad
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => Number(s))
      .filter((n) => Number.isFinite(n));

  const runPlanner = async () => {
    const ids = parseSquadIds();
    if (ids.length === 0) {
      setError('Enter your current 15 player IDs separated by commas');
      return;
    }
    setLoading(true);
    setError(null);
    setPlan(null);
    try {
      const req: TransferPlanRequest = {
        current_squad: ids,
        planning_horizon: planningHorizon,
        max_transfers_per_week: maxTransfersPerWeek,
      };
      const res = await apiClient.planTransfers(req);
      setPlan(res);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Planning failed');
    } finally {
      setLoading(false);
    }
  };

  const renderTransfer = (t: TransferOption) => (
    <div key={`${t.player_out_id}-${t.player_in_id}-${t.gameweek}`} className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded border">
      <div className="text-sm text-gray-900">GW{t.gameweek}: {t.player_out_id} → {t.player_in_id}</div>
      <div className="text-right text-sm">
        <div className="text-gray-900">+{t.expected_gain.toFixed(1)} pts</div>
        <div className="text-gray-500">Cost {t.cost}</div>
      </div>
    </div>
  );

  const renderWeek = (w: GameweekPlan) => (
    <div key={w.gameweek} className="bg-white rounded border p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">Gameweek {w.gameweek}</h3>
        <div className="text-xs text-gray-500">Net gain: {w.net_expected_gain.toFixed(1)} pts</div>
      </div>
      {w.transfers.length ? (
        <div className="space-y-2">{w.transfers.map(renderTransfer)}</div>
      ) : (
        <div className="text-sm text-gray-500">No transfers</div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
          <h1 className="text-2xl font-bold text-gray-900">Transfer Planner</h1>
          <p className="mt-1 text-sm text-gray-500">Plan your transfers across multiple gameweeks</p>
        </div>

        {/* Controls */}
        <div className="px-4 py-4 sm:px-6 border-b border-gray-100 space-y-4">
          <div>
            <label className="form-label">Current Squad (15 player IDs, comma-separated)</label>
            <textarea
              rows={2}
              className="form-input mt-1 w-full"
              placeholder="e.g. 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15"
              value={currentSquad}
              onChange={(e) => setCurrentSquad(e.target.value)}
            />
            <div className="text-xs text-gray-500 mt-1">Auto-filled from your current squad when available.</div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="form-label">Planning Horizon (GWs)</label>
              <input
                type="number"
                min={1}
                max={10}
                className="form-input mt-1"
                value={planningHorizon}
                onChange={(e) => setPlanningHorizon(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="form-label">Max Transfers / Week</label>
              <input
                type="number"
                min={0}
                max={5}
                className="form-input mt-1"
                value={maxTransfersPerWeek}
                onChange={(e) => setMaxTransfersPerWeek(Number(e.target.value))}
              />
            </div>
            <div className="flex">
              <button className="btn-primary w-full" onClick={runPlanner} disabled={loading}>
                {loading ? 'Planning…' : 'Plan Transfers'}
              </button>
            </div>
          </div>
        </div>

        <div className="px-4 py-5 sm:p-6">
          {loading && <LoadingSpinner />}
          {error && <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>}
          {!loading && !error && plan && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {plan.gameweek_plans.map(renderWeek)}
              </div>

              <div className="bg-gray-50 rounded p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <div className="text-sm text-gray-500">Total Expected Gain</div>
                  <div className="text-xl font-medium text-gray-900">{plan.total_expected_gain.toFixed(1)} pts</div>
                </div>
                <div>
                  <div className="text-sm text-gray-500">Total Transfer Costs</div>
                  <div className="text-xl font-medium text-gray-900">{plan.total_transfer_costs} pts</div>
                </div>
                <div>
                  <div className="text-sm text-gray-500">Horizon</div>
                  <div className="text-xl font-medium text-gray-900">{plan.planning_horizon} GWs</div>
                </div>
              </div>
            </div>
          )}
          {!loading && !error && !plan && (
            <div className="text-sm text-gray-500">Enter your current squad and click Plan Transfers.</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TransferPlanner;