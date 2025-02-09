import React, { useEffect, useState } from 'react';
import apiClient from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { OptimizationResult, SquadPlayer, TransferPlanRequest, TransferPlanResult } from '../types';

const Optimize: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [optResult, setOptResult] = useState<OptimizationResult | null>(null);
  const [plan, setPlan] = useState<TransferPlanResult | null>(null);
  const [captainSuggestion, setCaptainSuggestion] = useState<{ player_id: number; name?: string; predicted_points?: number } | null>(null);

  const gatherCurrentSquadIds = async (): Promise<number[]> => {
    const cur = await apiClient.getCurrentSquad();
    const ids: number[] = [
      ...(cur?.squad?.starting_xi?.map((p: any) => p.player_id) || []),
      ...(cur?.squad?.bench?.map((p: any) => p.player_id) || []),
    ];
    if (ids.length) return ids;
    const team = await apiClient.getTeamSummary();
    return [
      ...(team?.squad?.starting_xi?.map((p: any) => p.player_id) || []),
      ...(team?.squad?.bench?.map((p: any) => p.player_id) || []),
    ];
  };

  const optimizeLineup = async () => {
    setLoading(true);
    setError(null);
    setPlan(null);
    setCaptainSuggestion(null);
    try {
      const ids = await gatherCurrentSquadIds();
      // Uses formation endpoint to arrange best XI from current 15
      // First, we need some gameweek: use new team summary gw
      const summary = await apiClient.getTeamSummary();
      const res = await apiClient.optimizeFormation(ids, summary.gameweek || 1);
      setOptResult(res);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Optimization failed');
    } finally {
      setLoading(false);
    }
  };

  const suggestTransfers = async () => {
    setLoading(true);
    setError(null);
    setOptResult(null);
    setCaptainSuggestion(null);
    try {
      const ids = await gatherCurrentSquadIds();
      const req: TransferPlanRequest = { current_squad: ids, planning_horizon: 1, max_transfers_per_week: 1 };
      const res = await apiClient.planTransfers(req);
      setPlan(res);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Transfer suggestion failed');
    } finally {
      setLoading(false);
    }
  };

  const suggestCaptain = async () => {
    setLoading(true);
    setError(null);
    try {
      const ids = await gatherCurrentSquadIds();
      const res: any = await apiClient.optimizeCaptain(ids);
      setCaptainSuggestion(res?.best_captain || null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Captain suggestion failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
          <h1 className="text-2xl font-bold text-gray-900">Optimize</h1>
          <p className="mt-1 text-sm text-gray-500">Use your current squad to optimize lineup and suggest transfers for next GW</p>
        </div>

        <div className="px-4 py-5 sm:p-6 space-y-4">
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary" onClick={optimizeLineup} disabled={loading}>{loading ? 'Optimizing…' : 'Optimize Lineup'}</button>
            <button className="btn-secondary" onClick={suggestTransfers} disabled={loading}>{loading ? 'Working…' : 'Suggest Transfers'}</button>
            <button className="btn-secondary" onClick={suggestCaptain} disabled={loading}>{loading ? 'Analyzing…' : 'Suggest Captain'}</button>
          </div>

          {loading && <LoadingSpinner />}
          {error && <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>}

          {!loading && !error && optResult && (
            <div className="space-y-4">
              <div className="text-sm text-gray-500">Formation</div>
              <div className="text-lg font-medium">{optResult.formation}</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Predicted Points (XI)</div>
                  <div className="text-xl font-medium text-gray-900">{optResult.predicted_points.toFixed(1)}</div>
                </div>
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Total Cost</div>
                  <div className="text-xl font-medium text-gray-900">£{optResult.total_cost.toFixed(1)}M</div>
                </div>
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Captain</div>
                  <div className="text-xl font-medium text-gray-900">#{optResult.captain_id}</div>
                </div>
              </div>
            </div>
          )}

          {!loading && !error && plan && (
            <div className="space-y-3">
              <div className="text-sm font-medium text-gray-900">Suggested Transfers (Next GW)</div>
              <div className="space-y-2">
                {plan.gameweek_plans?.[0]?.transfers?.length ? plan.gameweek_plans[0].transfers.map((t) => (
                  <div key={`${t.player_out_id}-${t.player_in_id}`} className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded border">
                    <div className="text-sm text-gray-900">{t.player_out_id} → {t.player_in_id}</div>
                    <div className="text-right text-sm">
                      <div className="text-gray-900">+{t.expected_gain.toFixed(1)} pts</div>
                      <div className="text-gray-500">Cost {t.cost}</div>
                    </div>
                  </div>
                )) : (
                  <div className="text-sm text-gray-500">No transfers suggested</div>
                )}
              </div>
            </div>
          )}

          {!loading && !error && captainSuggestion && (
            <div className="bg-gray-50 rounded p-4">
              <div className="text-sm text-gray-500">Suggested Captain</div>
              <div className="text-lg font-medium text-gray-900">#{captainSuggestion.player_id} {captainSuggestion.name ? `- ${captainSuggestion.name}` : ''}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Optimize;


