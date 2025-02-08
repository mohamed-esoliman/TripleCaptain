import React, { useEffect, useMemo, useState } from 'react';
import apiClient from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import PlayerCard from '../components/common/PlayerCard';
import { Player, PlayersResponse, PlayerFilters, Position, POSITION_SHORT_NAMES, Team, PlayerDetail } from '../types';

const PAGE_SIZE = 25;

const PlayersPage: React.FC = () => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Player | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<PlayerDetail | null>(null);
  const [selectedFixtures, setSelectedFixtures] = useState<any[] | null>(null);

  const [filters, setFilters] = useState<PlayerFilters>({
    available_only: true,
    status: 'a',
  });

  useEffect(() => {
    let mounted = true;

    const loadTeams = async () => {
      try {
        const t = await apiClient.getTeams();
        if (mounted) setTeams(t);
      } catch (e) {
        // ignore team load errors for now
      }
    };

    loadTeams();
    return () => {
      mounted = false;
    };
  }, []);

  const fetchPlayers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res: PlayersResponse = await apiClient.getPlayers(filters, page, PAGE_SIZE);
      setPlayers(res.players);
      setTotal(res.total);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load players');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlayers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, JSON.stringify(filters)]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  const updateFilter = (patch: Partial<PlayerFilters>) => {
    setPage(1);
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  const teamName = (teamId: number) => teams.find((t) => t.id === teamId)?.short_name || `T${teamId}`;

  const openInspect = async (p: Player) => {
    setSelected(p);
    setSelectedDetail(null);
    setSelectedFixtures(null);
    try {
      const [detail, fixtures] = await Promise.all([
        apiClient.getPlayer(p.id) as unknown as Promise<PlayerDetail>,
        apiClient.getPlayerFixtures(p.id),
      ]);
      setSelectedDetail(detail);
      setSelectedFixtures(fixtures);
    } catch (e) {
      // ignore
    }
  };
  const closeInspect = () => {
    setSelected(null);
    setSelectedDetail(null);
    setSelectedFixtures(null);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
          <h1 className="text-2xl font-bold text-gray-900">Player Analysis</h1>
          <p className="mt-1 text-sm text-gray-500">Explore detailed player statistics and AI predictions</p>
        </div>

        {/* Filters */}
        <div className="px-4 py-4 sm:px-6 border-b border-gray-100">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
            <div>
              <label className="form-label">Position</label>
              <select
                className="form-input mt-1"
                value={filters.position ?? ''}
                onChange={(e) =>
                  updateFilter({ position: e.target.value ? Number(e.target.value) as Position : undefined })
                }
              >
                <option value="">All</option>
                <option value={Position.GOALKEEPER}>GKP</option>
                <option value={Position.DEFENDER}>DEF</option>
                <option value={Position.MIDFIELDER}>MID</option>
                <option value={Position.FORWARD}>FWD</option>
              </select>
            </div>

            <div>
              <label className="form-label">Team</label>
              <select
                className="form-input mt-1"
                value={filters.team_id ?? ''}
                onChange={(e) => updateFilter({ team_id: e.target.value ? Number(e.target.value) : undefined })}
              >
                <option value="">All</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.short_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="form-label">Min Points</label>
              <input
                type="number"
                className="form-input mt-1"
                value={filters.min_points ?? ''}
                onChange={(e) => updateFilter({ min_points: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="e.g. 50"
              />
            </div>

            <div>
              <label className="form-label">Price (M)</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  className="form-input mt-1"
                  value={filters.min_price ?? ''}
                  onChange={(e) => updateFilter({ min_price: e.target.value ? Number(e.target.value) : undefined })}
                  placeholder="min"
                  step="0.1"
                />
                <input
                  type="number"
                  className="form-input mt-1"
                  value={filters.max_price ?? ''}
                  onChange={(e) => updateFilter({ max_price: e.target.value ? Number(e.target.value) : undefined })}
                  placeholder="max"
                  step="0.1"
                />
              </div>
            </div>

            <div>
              <label className="form-label">Availability</label>
              <select
                className="form-input mt-1"
                value={filters.status ?? 'a'}
                onChange={(e) => updateFilter({ status: e.target.value || undefined, available_only: e.target.value ? true : undefined })}
              >
                <option value="">Any</option>
                <option value="a">Available</option>
                <option value="i">Injured</option>
                <option value="s">Suspended</option>
                <option value="u">Unavailable</option>
              </select>
            </div>
          </div>
        </div>

        <div className="px-4 py-5 sm:p-6">
          {loading ? (
            <LoadingSpinner />
          ) : error ? (
            <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pos</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Team</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Pts</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Form</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">EP Next</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {players.map((p) => (
                    <tr key={p.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => openInspect(p)}>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                        {(p.first_name || '') + ' ' + p.second_name}
                        <div className="text-xs text-gray-500">{p.web_name}</div>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{POSITION_SHORT_NAMES[p.position]}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{teamName(p.team_id)}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 text-right">{(p.current_price / 10).toFixed(1)}M</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 text-right">{p.total_points}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 text-right">{p.form?.toFixed?.(1) ?? p.form}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 text-right">{p.ep_next?.toFixed?.(1) ?? p.ep_next}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm">
                        {p.status === 'a' ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Available</span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                            {p.status}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              <div className="mt-4 flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  Page {page} of {totalPages} ({total} results)
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn-secondary"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <button
                    className="btn-primary"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      {/* Inspect Drawer */}
      {selected && (
        <div className="fixed inset-0 z-30">
          <div className="absolute inset-0 bg-black/30" onClick={closeInspect} />
          <div className="absolute right-0 top-0 h-full w-full sm:w-[28rem] bg-white shadow-xl p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-medium text-gray-900">Player Details</h3>
              <button className="text-gray-500 hover:text-gray-700" onClick={closeInspect}>✕</button>
            </div>
            <PlayerCard
              player={{
                id: selected.id,
                web_name: selected.web_name,
                position: selected.position,
                team_id: selected.team_id,
                current_price: (selected.current_price / 10),
                name: (selected.first_name || '') + ' ' + selected.second_name,
              }}
            />
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded bg-gray-50 p-3">
                <div className="text-xs text-gray-500">Total Points</div>
                <div className="text-base font-medium">{selected.total_points}</div>
              </div>
              <div className="rounded bg-gray-50 p-3">
                <div className="text-xs text-gray-500">Form</div>
                <div className="text-base font-medium">{selected.form}</div>
              </div>
            </div>
            {selectedDetail && (
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">Influence</div>
                  <div className="text-base font-medium">{selectedDetail.influence}</div>
                </div>
                <div className="rounded bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">Creativity</div>
                  <div className="text-base font-medium">{selectedDetail.creativity}</div>
                </div>
              </div>
            )}
            <div className="mt-6">
              <div className="text-sm font-medium text-gray-900 mb-2">Upcoming Fixtures</div>
              <div className="space-y-2">
                {(selectedFixtures || []).map((f, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm">
                    <div>GW {f.gameweek} {f.is_home ? 'vs' : '@'} {f.opponent_team_id}</div>
                    <div className="text-gray-500">Diff {f.difficulty}</div>
                  </div>
                ))}
                {!selectedFixtures && (
                  <div className="text-xs text-gray-500">Loading fixtures…</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlayersPage;