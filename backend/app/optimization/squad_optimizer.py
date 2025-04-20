import pulp
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

from app.db.models import Player, MLPrediction

logger = logging.getLogger(__name__)


class Position(Enum):
    GOALKEEPER = 1
    DEFENDER = 2
    MIDFIELDER = 3
    FORWARD = 4


class Formation(Enum):
    FORMATION_3_4_3 = "3-4-3"
    FORMATION_3_5_2 = "3-5-2"
    FORMATION_4_3_3 = "4-3-3"
    FORMATION_4_4_2 = "4-4-2"
    FORMATION_4_5_1 = "4-5-1"
    FORMATION_5_3_2 = "5-3-2"
    FORMATION_5_4_1 = "5-4-1"


@dataclass
class PlayerData:
    """Player data for optimization."""

    id: int
    position: int
    team_id: int
    price: float  # In millions
    predicted_points: float
    start_probability: float
    name: str
    variance: float = 0.0
    ceiling_points: float = 0.0
    floor_points: float = 0.0


@dataclass
class OptimizationConstraints:
    """Constraints for squad optimization."""

    budget: float = 100.0  # Budget in millions
    squad_size: int = 15
    starting_xi_size: int = 11
    max_players_per_team: int = 3
    formation: Optional[str] = None
    excluded_players: List[int] = None
    required_players: List[int] = None
    risk_tolerance: float = 0.5  # 0 = risk-averse, 1 = risk-seeking


@dataclass
class FormationConstraints:
    """Formation-specific constraints."""

    goalkeepers: int = 1
    defenders: Tuple[int, int] = (3, 5)  # min, max
    midfielders: Tuple[int, int] = (2, 5)  # min, max
    forwards: Tuple[int, int] = (1, 3)  # min, max


FORMATION_CONSTRAINTS = {
    "3-4-3": FormationConstraints(1, (3, 3), (4, 4), (3, 3)),
    "3-5-2": FormationConstraints(1, (3, 3), (5, 5), (2, 2)),
    "4-3-3": FormationConstraints(1, (4, 4), (3, 3), (3, 3)),
    "4-4-2": FormationConstraints(1, (4, 4), (4, 4), (2, 2)),
    "4-5-1": FormationConstraints(1, (4, 4), (5, 5), (1, 1)),
    "5-3-2": FormationConstraints(1, (5, 5), (3, 3), (2, 2)),
    "5-4-1": FormationConstraints(1, (5, 5), (4, 4), (1, 1)),
}


class SquadOptimizer:
    """Optimize FPL squad selection using linear programming."""

    def __init__(self):
        self.solver = pulp.PULP_CBC_CMD(msg=0)  # Silent solver

    def optimize_squad(
        self, players: List[PlayerData], constraints: OptimizationConstraints
    ) -> Dict[str, Any]:
        """Optimize squad selection."""

        logger.info(f"Optimizing squad with {len(players)} players")

        # Create optimization problem
        prob = pulp.LpProblem("FPL_Squad_Selection", pulp.LpMaximize)

        # Decision variables
        # x[i] = 1 if player i is selected for squad, 0 otherwise
        squad_vars = {
            player.id: pulp.LpVariable(f"squad_{player.id}", cat="Binary")
            for player in players
        }

        # s[i] = 1 if player i is in starting XI, 0 otherwise
        starting_vars = {
            player.id: pulp.LpVariable(f"starting_{player.id}", cat="Binary")
            for player in players
        }

        # c[i] = 1 if player i is captain, 0 otherwise
        captain_vars = {
            player.id: pulp.LpVariable(f"captain_{player.id}", cat="Binary")
            for player in players
        }

        # Objective function - maximize expected points
        objective_terms = []

        for player in players:
            player_id = player.id

            # Base points for starting
            base_points = player.predicted_points * player.start_probability
            objective_terms.append(base_points * starting_vars[player_id])

            # Captain bonus (double points)
            captain_bonus = player.predicted_points * player.start_probability
            objective_terms.append(captain_bonus * captain_vars[player_id])

            # Risk adjustment
            if constraints.risk_tolerance < 0.5:
                # Risk-averse: penalize variance
                risk_penalty = player.variance * (0.5 - constraints.risk_tolerance) * 2
                objective_terms.append(-risk_penalty * starting_vars[player_id])
            elif constraints.risk_tolerance > 0.5:
                # Risk-seeking: reward variance
                risk_bonus = player.variance * (constraints.risk_tolerance - 0.5) * 2
                objective_terms.append(risk_bonus * starting_vars[player_id])

        prob += pulp.lpSum(objective_terms)

        # Constraints
        self._add_squad_constraints(
            prob, players, constraints, squad_vars, starting_vars, captain_vars
        )

        # Solve the problem
        prob.solve(self.solver)

        # Extract solution
        if prob.status == pulp.LpStatusOptimal:
            return self._extract_solution(
                players, squad_vars, starting_vars, captain_vars, constraints
            )
        else:
            raise ValueError(
                f"Optimization failed with status: {pulp.LpStatus[prob.status]}"
            )

    def _add_squad_constraints(
        self,
        prob: pulp.LpProblem,
        players: List[PlayerData],
        constraints: OptimizationConstraints,
        squad_vars: Dict[int, pulp.LpVariable],
        starting_vars: Dict[int, pulp.LpVariable],
        captain_vars: Dict[int, pulp.LpVariable],
    ):
        """Add all optimization constraints."""

        # Budget constraint
        budget_terms = [player.price * squad_vars[player.id] for player in players]
        prob += pulp.lpSum(budget_terms) <= constraints.budget

        # Squad size constraint
        prob += pulp.lpSum(squad_vars.values()) == constraints.squad_size

        # Starting XI size constraint
        prob += pulp.lpSum(starting_vars.values()) == constraints.starting_xi_size

        # Captain constraint (exactly one)
        prob += pulp.lpSum(captain_vars.values()) == 1

        # Linking constraints
        for player in players:
            player_id = player.id
            # Can't start without being in squad
            prob += starting_vars[player_id] <= squad_vars[player_id]
            # Can't be captain without starting
            prob += captain_vars[player_id] <= starting_vars[player_id]

        # Position constraints for squad
        players_by_position = self._group_players_by_position(players)

        # Only enforce 2/5/5/3 when building the full 15-man squad
        if constraints.squad_size == 15:
            # Goalkeepers: exactly 2
            gk_squad = [
                squad_vars[p.id] for p in players_by_position[Position.GOALKEEPER.value]
            ]
            prob += pulp.lpSum(gk_squad) == 2

            # Defenders: exactly 5
            def_squad = [
                squad_vars[p.id] for p in players_by_position[Position.DEFENDER.value]
            ]
            prob += pulp.lpSum(def_squad) == 5

            # Midfielders: exactly 5
            mid_squad = [
                squad_vars[p.id] for p in players_by_position[Position.MIDFIELDER.value]
            ]
            prob += pulp.lpSum(mid_squad) == 5

            # Forwards: exactly 3
            fwd_squad = [
                squad_vars[p.id] for p in players_by_position[Position.FORWARD.value]
            ]
            prob += pulp.lpSum(fwd_squad) == 3

        # Formation constraints for starting XI
        if constraints.formation and constraints.formation in FORMATION_CONSTRAINTS:
            formation_constraint = FORMATION_CONSTRAINTS[constraints.formation]

            # Starting goalkeepers: exactly 1
            gk_starting = [
                starting_vars[p.id]
                for p in players_by_position[Position.GOALKEEPER.value]
            ]
            prob += pulp.lpSum(gk_starting) == formation_constraint.goalkeepers

            # Starting defenders
            def_starting = [
                starting_vars[p.id]
                for p in players_by_position[Position.DEFENDER.value]
            ]
            min_def, max_def = formation_constraint.defenders
            prob += pulp.lpSum(def_starting) >= min_def
            prob += pulp.lpSum(def_starting) <= max_def

            # Starting midfielders
            mid_starting = [
                starting_vars[p.id]
                for p in players_by_position[Position.MIDFIELDER.value]
            ]
            min_mid, max_mid = formation_constraint.midfielders
            prob += pulp.lpSum(mid_starting) >= min_mid
            prob += pulp.lpSum(mid_starting) <= max_mid

            # Starting forwards
            fwd_starting = [
                starting_vars[p.id] for p in players_by_position[Position.FORWARD.value]
            ]
            min_fwd, max_fwd = formation_constraint.forwards
            prob += pulp.lpSum(fwd_starting) >= min_fwd
            prob += pulp.lpSum(fwd_starting) <= max_fwd
        else:
            # General formation constraints if no specific formation
            gk_starting = [
                starting_vars[p.id]
                for p in players_by_position[Position.GOALKEEPER.value]
            ]
            prob += pulp.lpSum(gk_starting) == 1

            def_starting = [
                starting_vars[p.id]
                for p in players_by_position[Position.DEFENDER.value]
            ]
            prob += pulp.lpSum(def_starting) >= 3
            prob += pulp.lpSum(def_starting) <= 5

            mid_starting = [
                starting_vars[p.id]
                for p in players_by_position[Position.MIDFIELDER.value]
            ]
            prob += pulp.lpSum(mid_starting) >= 2
            prob += pulp.lpSum(mid_starting) <= 5

            fwd_starting = [
                starting_vars[p.id] for p in players_by_position[Position.FORWARD.value]
            ]
            prob += pulp.lpSum(fwd_starting) >= 1
            prob += pulp.lpSum(fwd_starting) <= 3

        # Team constraints - max 3 players per team
        players_by_team = {}
        for player in players:
            if player.team_id not in players_by_team:
                players_by_team[player.team_id] = []
            players_by_team[player.team_id].append(player)

        for team_id, team_players in players_by_team.items():
            team_vars = [squad_vars[p.id] for p in team_players]
            prob += pulp.lpSum(team_vars) <= constraints.max_players_per_team

        # Excluded players
        if constraints.excluded_players:
            for player_id in constraints.excluded_players:
                if player_id in squad_vars:
                    prob += squad_vars[player_id] == 0

        # Required players
        if constraints.required_players:
            for player_id in constraints.required_players:
                if player_id in squad_vars:
                    prob += squad_vars[player_id] == 1

    def _group_players_by_position(
        self, players: List[PlayerData]
    ) -> Dict[int, List[PlayerData]]:
        """Group players by position."""
        grouped = {1: [], 2: [], 3: [], 4: []}
        for player in players:
            if player.position in grouped:
                grouped[player.position].append(player)
        return grouped

    def _extract_solution(
        self,
        players: List[PlayerData],
        squad_vars: Dict[int, pulp.LpVariable],
        starting_vars: Dict[int, pulp.LpVariable],
        captain_vars: Dict[int, pulp.LpVariable],
        constraints: OptimizationConstraints,
    ) -> Dict[str, Any]:
        """Extract solution from optimization variables."""

        # Get selected players
        squad_players = []
        starting_players = []
        bench_players = []
        captain_id = None

        total_cost = 0.0
        total_predicted_points = 0.0

        for player in players:
            player_id = player.id

            if squad_vars[player_id].varValue == 1:
                squad_players.append(player)
                total_cost += player.price

                if starting_vars[player_id].varValue == 1:
                    starting_players.append(player)
                    total_predicted_points += (
                        player.predicted_points * player.start_probability
                    )

                    if captain_vars[player_id].varValue == 1:
                        captain_id = player_id
                        # Add captain bonus
                        total_predicted_points += (
                            player.predicted_points * player.start_probability
                        )
                else:
                    bench_players.append(player)

        # Determine formation
        formation = self._determine_formation(starting_players)

        # Generate alternative solutions
        alternatives = self._generate_alternatives(players, constraints)

        return {
            "squad": [
                self._player_to_dict(p, p in starting_players, p.id == captain_id)
                for p in squad_players
            ],
            "starting_xi": [
                self._player_to_dict(p, True, p.id == captain_id)
                for p in starting_players
            ],
            "bench": [self._player_to_dict(p, False, False) for p in bench_players],
            "formation": formation,
            "total_cost": round(total_cost, 1),
            "predicted_points": round(total_predicted_points, 1),
            "captain_id": captain_id,
            "alternatives": alternatives[:3],  # Top 3 alternatives
        }

    def _player_to_dict(
        self, player: PlayerData, is_starter: bool, is_captain: bool
    ) -> Dict[str, Any]:
        """Convert player data to dictionary."""
        return {
            "player_id": player.id,
            "name": player.name,
            "position": player.position,
            "team_id": player.team_id,
            "price": player.price,
            "predicted_points": round(player.predicted_points, 1),
            "start_probability": round(player.start_probability, 2),
            "is_starter": is_starter,
            "is_captain": is_captain,
            "variance": round(player.variance, 2),
        }

    def _determine_formation(self, starting_players: List[PlayerData]) -> str:
        """Determine formation from starting XI."""
        position_counts = {1: 0, 2: 0, 3: 0, 4: 0}

        for player in starting_players:
            position_counts[player.position] += 1

        # Format as string (excluding goalkeeper)
        def_count = position_counts[2]
        mid_count = position_counts[3]
        fwd_count = position_counts[4]

        return f"{def_count}-{mid_count}-{fwd_count}"

    def _generate_alternatives(
        self,
        players: List[PlayerData],
        constraints: OptimizationConstraints,
        num_alternatives: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate alternative squad solutions."""
        alternatives = []

        # For now, return empty alternatives
        # In a full implementation, this would run multiple optimizations
        # with slightly different constraints or objective functions

        return alternatives

    def find_best_formation(
        self, players: List[PlayerData], constraints: OptimizationConstraints
    ) -> Dict[str, Any]:
        """Find the best formation for given players and constraints."""

        best_formation = None
        best_points = 0
        best_result = None
        formation_results = {}

        for formation_name in FORMATION_CONSTRAINTS.keys():
            try:
                formation_constraints = OptimizationConstraints(
                    budget=constraints.budget,
                    squad_size=constraints.squad_size,
                    starting_xi_size=constraints.starting_xi_size,
                    max_players_per_team=constraints.max_players_per_team,
                    formation=formation_name,
                    excluded_players=constraints.excluded_players,
                    required_players=constraints.required_players,
                    risk_tolerance=constraints.risk_tolerance,
                )

                result = self.optimize_squad(players, formation_constraints)
                formation_results[formation_name] = result

                if result["predicted_points"] > best_points:
                    best_points = result["predicted_points"]
                    best_formation = formation_name
                    best_result = result

            except Exception as e:
                logger.warning(f"Formation {formation_name} optimization failed: {e}")
                continue

        return {
            "best_formation": best_formation,
            "best_result": best_result,
            "all_formations": formation_results,
        }

    def optimize_captain_choice(
        self, players: List[PlayerData], current_squad: List[int]
    ) -> Dict[str, Any]:
        """Optimize captain choice for a given squad."""

        squad_players = [p for p in players if p.id in current_squad]

        if not squad_players:
            return {"error": "No players in current squad"}

        # Calculate expected points for each potential captain
        captain_options = []

        for player in squad_players:
            # Expected points with captain bonus
            expected_points = player.predicted_points * player.start_probability * 2

            # Risk-adjusted expected points
            risk_adjustment = player.variance * 0.1  # Small penalty for high variance
            adjusted_points = expected_points - risk_adjustment

            captain_options.append(
                {
                    "player_id": player.id,
                    "name": player.name,
                    "position": player.position,
                    "expected_points": round(expected_points, 1),
                    "risk_adjusted_points": round(adjusted_points, 1),
                    "start_probability": round(player.start_probability, 2),
                    "base_points": round(player.predicted_points, 1),
                    "variance": round(player.variance, 2),
                }
            )

        # Sort by risk-adjusted expected points
        captain_options.sort(key=lambda x: x["risk_adjusted_points"], reverse=True)

        return {
            "recommended_captain": captain_options[0],
            "top_options": captain_options[:5],
            "all_options": captain_options,
        }
