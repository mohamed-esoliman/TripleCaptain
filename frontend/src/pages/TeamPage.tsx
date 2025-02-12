import React, { useEffect, useMemo, useState } from 'react';
import apiClient from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import FormationPitch from '../components/common/FormationPitch';
import { SquadPlayer, TeamSummary } from '../types';

const TeamPage: React.FC = () => {
  const [summary, setSummary] = useState<TeamSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | undefined>(undefined);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        // cache teams for PlayerCard labels
        const teams = await apiClient.getTeams();
        try { localStorage.setItem('__tc_teams', JSON.stringify(teams)); } catch {}
        const data = await apiClient.getTeamSummary();
        setSummary(data);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Failed to load team summary');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Prefer factual GW points if provided; preserve structure
  const starters: SquadPlayer[] = useMemo(() => {
    const list = (summary?.squad.starting_xi || []) as any[];
    return list.map((p) => ({ ...p }));
  }, [summary]);
  const bench: SquadPlayer[] = useMemo(() => {
    const list = (summary?.squad.bench || []) as any[];
    return list.map((p) => ({ ...p }));
  }, [summary]);

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
          <h1 className="text-2xl font-bold text-gray-900">My Team</h1>
          <p className="mt-1 text-sm text-gray-500">Your current squad, value, and performance</p>
        </div>

        <div className="px-4 py-5 sm:p-6 space-y-6">
          {loading && <LoadingSpinner />}
          {error && <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>}
          {!loading && !error && summary && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Gameweek</div>
                  <div className="text-xl font-medium text-gray-900">{summary.gameweek}</div>
                </div>
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">GW Points</div>
                  <div className="text-xl font-medium text-gray-900">{summary.gw_points}</div>
                </div>
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Total Points</div>
                  <div className="text-xl font-medium text-gray-900">{summary.total_points}</div>
                </div>
                <div className="bg-gray-50 rounded p-4">
                  <div className="text-sm text-gray-500">Overall Rank</div>
                  <div className="text-xl font-medium text-gray-900">{summary.overall_rank ?? '—'}</div>
                </div>
              </div>

              <div>
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-sm text-gray-500">Formation</div>
                  <div className="text-sm font-medium text-gray-900">{summary.formation}</div>
                </div>
                <FormationPitch
                  starters={starters}
                  formation={summary.formation}
                  onSelect={(p) => setSelectedId(p.player_id)}
                  selectedId={selectedId}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white border rounded p-4">
                  <div className="text-sm font-medium text-gray-900 mb-2">Bench</div>
                  <div className="space-y-2">
                    {bench.length ? (
                      bench.map((p: any) => (
                        <div key={p.player_id} className="text-sm text-gray-700 flex items-center justify-between border rounded px-3 py-2">
                          <div>{p.name}</div>
                          <div className="text-gray-500">{p.gw_points != null ? (Number.isFinite(p.gw_points) ? `${(p.gw_points as number).toFixed?.(1) ?? p.gw_points} pts` : '—') : '—'}</div>
                        </div>
                      ))
                    ) : (
                      <div className="text-sm text-gray-500">No bench data</div>
                    )}
                  </div>
                </div>
                <div className="bg-white border rounded p-4">
                  <div className="text-sm font-medium text-gray-900 mb-2">Finance</div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="bg-gray-50 rounded p-3">
                      <div className="text-gray-500">Team Value</div>
                      <div className="text-gray-900 font-medium">£{summary.team_value.toFixed(1)}M</div>
                    </div>
                    <div className="bg-gray-50 rounded p-3">
                      <div className="text-gray-500">Bank</div>
                      <div className="text-gray-900 font-medium">{summary.bank !== undefined ? `£${summary.bank?.toFixed(1)}M` : '—'}</div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TeamPage;


