import React from 'react';
import PlayerCard from './PlayerCard';
import { Position, SquadPlayer } from '../../types';

interface Props {
  starters: SquadPlayer[];
  formation: string; // e.g. 3-4-3
  onSelect?: (p: SquadPlayer) => void;
  selectedId?: number;
}

function groupByPosition(players: SquadPlayer[]) {
  return {
    gkp: players.filter((p) => p.position === Position.GOALKEEPER),
    def: players.filter((p) => p.position === Position.DEFENDER),
    mid: players.filter((p) => p.position === Position.MIDFIELDER),
    fwd: players.filter((p) => p.position === Position.FORWARD),
  };
}

const FormationPitch: React.FC<Props> = ({ starters, formation, onSelect, selectedId }) => {
  const { gkp, def, mid, fwd } = groupByPosition(starters);
  const [d, m, f] = formation.split('-').map((x) => parseInt(x, 10));

  const rows: { label: string; list: SquadPlayer[] }[] = [
    { label: 'GKP', list: gkp.slice(0, 1) },
    { label: 'DEF', list: def.slice(0, d) },
    { label: 'MID', list: mid.slice(0, m) },
    { label: 'FWD', list: fwd.slice(0, f) },
  ];

  return (
    <div className="relative rounded-lg p-4" style={{ background: 'linear-gradient(#2f855a, #276749)' }}>
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute left-4 right-4 top-1/2 border-t border-white/30" />
        <div className="absolute inset-4 rounded border border-white/30" />
      </div>
      <div className="space-y-4">
        {rows.map((row, idx) => (
          <div key={idx} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {row.list.map((p) => (
              <div key={p.player_id} className={selectedId === p.player_id ? 'ring-2 ring-indigo-400 rounded' : ''}>
                <PlayerCard
                  player={{
                    player_id: p.player_id,
                    position: p.position,
                    team_id: p.team_id,
                    current_price: p.price,
                    gw_points: (p as any).gw_points,
                    predicted_points: p.predicted_points,
                    is_captain: p.is_captain,
                    name: p.name,
                  }}
                  compact
                  highlight={selectedId === p.player_id}
                  onClick={() => onSelect?.(p)}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};

export default FormationPitch;


