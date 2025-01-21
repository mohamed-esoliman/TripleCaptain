import React, { useMemo } from 'react';
import { Player, Position, POSITION_SHORT_NAMES, Team } from '../../types';

type PlayerLike = Partial<Player> & {
  id?: number;
  player_id?: number;
  name?: string;
  web_name?: string;
  position?: Position;
  team_id?: number;
  current_price?: number;
  price?: number;
  predicted_points?: number;
  gw_points?: number | null;
  is_captain?: boolean;
  is_vice_captain?: boolean;
};

interface Props {
  player: PlayerLike;
  onClick?: () => void;
  compact?: boolean;
  highlight?: boolean;
}

const PlayerCard: React.FC<Props> = ({ player, onClick, compact = false, highlight = false }) => {
  const name = player.name || player.web_name || `#${player.player_id || player.id}`;
  const pos = player.position as Position | undefined;
  const priceM = typeof player.current_price === 'number' ? player.current_price : (player.price ?? 0);
  const gw = (player as any).gw_points as number | undefined;
  const predicted = (player as any).predicted_points as number | undefined;
  const teamsCacheKey = '__tc_teams';
  const teamsMap = useMemo(() => {
    try {
      const raw = localStorage.getItem(teamsCacheKey);
      if (!raw) return {} as Record<number, string>;
      const list: Team[] = JSON.parse(raw);
      const map: Record<number, string> = {};
      list.forEach((t) => (map[t.id] = t.short_name || t.name));
      return map;
    } catch {
      return {} as Record<number, string>;
    }
  }, []);
  const teamLabel = player.team_id != null ? (teamsMap[player.team_id] || `Team ${player.team_id}`) : '—';

  return (
    <div
      onClick={onClick}
      className={
        `cursor-pointer select-none rounded border ${highlight ? 'border-indigo-500 ring-2 ring-indigo-200' : 'border-gray-200'} ` +
        `${compact ? 'p-2' : 'p-3'} bg-white shadow-sm hover:shadow`}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-gray-900">{name}</div>
          <div className="text-xs text-gray-500">
            {pos ? POSITION_SHORT_NAMES[pos] : '—'} • {teamLabel}
          </div>
        </div>
        <div className="text-right">
          {gw != null ? (
            <div className="text-sm text-gray-900">{Number.isFinite(gw) ? `${gw.toFixed?.(1) ?? gw} pts` : '—'}</div>
          ) : (
            typeof predicted === 'number' && (
              <div className="text-sm text-gray-900">{predicted.toFixed(1)} pts</div>
            )
          )}
          <div className="text-xs text-gray-500">£{Number(priceM).toFixed(1)}M</div>
          {(player as any).is_captain && (
            <div className="mt-1 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-yellow-100 text-yellow-800">C</div>
          )}
          {(player as any).is_vice_captain && !((player as any).is_captain) && (
            <div className="mt-1 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-indigo-100 text-indigo-800">VC</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PlayerCard;


