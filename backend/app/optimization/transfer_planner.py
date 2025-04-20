import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from app.optimization.squad_optimizer import PlayerData, OptimizationConstraints, SquadOptimizer

logger = logging.getLogger(__name__)


@dataclass
class TransferOption:
    """Represents a potential transfer."""
    player_out_id: int
    player_in_id: int
    cost: int  # Transfer cost in points (-4 for additional transfers)
    expected_gain: float  # Expected points gain
    price_change: float  # Expected price change
    gameweek: int
    
    
@dataclass
class GameweekPlan:
    """Plan for a specific gameweek."""
    gameweek: int
    transfers: List[TransferOption]
    expected_points: float
    squad_value: float
    free_transfers: int
    total_transfer_cost: int
    
    
@dataclass
class ChipStrategy:
    """Strategy for using chips."""
    chip_type: str  # 'wildcard', 'bench_boost', 'triple_captain', 'free_hit'
    recommended_gameweek: Optional[int]
    expected_benefit: float
    confidence: float
    
    
class TransferPlanner:
    """Multi-gameweek transfer planning with dynamic programming."""
    
    def __init__(self, squad_optimizer: SquadOptimizer):
        self.optimizer = squad_optimizer
        
    def plan_transfers(
        self,
        current_squad: List[PlayerData],
        all_players: List[PlayerData],
        planning_horizon: int = 5,
        max_transfers_per_week: int = 1,
        available_chips: Dict[str, bool] = None,
        current_gameweek: int = 1
    ) -> Dict[str, Any]:
        """Plan transfers for multiple gameweeks ahead."""
        
        logger.info(f"Planning transfers for {planning_horizon} gameweeks")
        
        if available_chips is None:
            available_chips = {
                'wildcard': False,
                'bench_boost': False,
                'triple_captain': False,
                'free_hit': False
            }
            
        # Initialize state
        current_state = {
            'squad': current_squad.copy(),
            'gameweek': current_gameweek,
            'free_transfers': 1,  # Assume 1 free transfer available
            'squad_value': sum(p.price for p in current_squad),
            'chips_used': []
        }
        
        # Plan for each gameweek
        gameweek_plans = []
        
        for week_offset in range(planning_horizon):
            target_gameweek = current_gameweek + week_offset
            
            # Get best transfers for this gameweek
            week_plan = self._plan_single_gameweek(
                current_state,
                all_players,
                target_gameweek,
                max_transfers_per_week,
                available_chips
            )
            
            gameweek_plans.append(week_plan)
            
            # Update state for next gameweek
            current_state = self._update_state(current_state, week_plan)
            
        # Analyze chip usage
        chip_recommendations = self._analyze_chip_usage(
            gameweek_plans,
            available_chips,
            current_gameweek,
            planning_horizon
        )
        
        # Calculate total expected gain
        total_expected_gain = sum(plan.expected_points for plan in gameweek_plans)
        total_transfer_costs = sum(plan.total_transfer_cost for plan in gameweek_plans)
        
        return {
            'gameweek_plans': [self._gameweek_plan_to_dict(plan) for plan in gameweek_plans],
            'chip_recommendations': chip_recommendations,
            'total_expected_gain': round(total_expected_gain - total_transfer_costs, 1),
            'total_transfer_costs': total_transfer_costs,
            'planning_horizon': planning_horizon
        }
        
    def _plan_single_gameweek(
        self,
        current_state: Dict[str, Any],
        all_players: List[PlayerData],
        gameweek: int,
        max_transfers: int,
        available_chips: Dict[str, bool]
    ) -> GameweekPlan:
        """Plan transfers for a single gameweek."""
        
        current_squad = current_state['squad']
        free_transfers = current_state['free_transfers']
        
        # Find best transfer options
        transfer_options = self._find_transfer_options(
            current_squad,
            all_players,
            gameweek
        )
        
        # Select best transfers within constraints
        selected_transfers = self._select_transfers(
            transfer_options,
            max_transfers,
            free_transfers
        )
        
        # Calculate expected points for the resulting squad
        new_squad = self._apply_transfers(current_squad, selected_transfers)
        expected_points = self._calculate_squad_expected_points(new_squad)
        
        # Calculate transfer costs
        num_transfers = len(selected_transfers)
        transfer_cost = max(0, (num_transfers - free_transfers) * 4)
        
        return GameweekPlan(
            gameweek=gameweek,
            transfers=selected_transfers,
            expected_points=expected_points,
            squad_value=sum(p.price for p in new_squad),
            free_transfers=free_transfers,
            total_transfer_cost=transfer_cost
        )
        
    def _find_transfer_options(
        self,
        current_squad: List[PlayerData],
        all_players: List[PlayerData],
        gameweek: int
    ) -> List[TransferOption]:
        """Find all viable transfer options."""
        
        transfer_options = []
        squad_player_ids = {p.id for p in current_squad}
        available_players = [p for p in all_players if p.id not in squad_player_ids]
        
        # Consider each player in current squad for transfer out
        for current_player in current_squad:
            # Find suitable replacements in same position
            position_replacements = [
                p for p in available_players 
                if p.position == current_player.position
            ]
            
            for replacement in position_replacements:
                # Calculate expected gain
                points_gain = (replacement.predicted_points * replacement.start_probability) - \
                             (current_player.predicted_points * current_player.start_probability)
                
                # Consider price change (simplified)
                price_change = 0.0  # TODO: Implement price prediction
                
                transfer_option = TransferOption(
                    player_out_id=current_player.id,
                    player_in_id=replacement.id,
                    cost=4,  # Standard transfer cost
                    expected_gain=points_gain,
                    price_change=price_change,
                    gameweek=gameweek
                )
                
                transfer_options.append(transfer_option)
                
        # Sort by expected gain
        transfer_options.sort(key=lambda x: x.expected_gain, reverse=True)
        
        return transfer_options
        
    def _select_transfers(
        self,
        transfer_options: List[TransferOption],
        max_transfers: int,
        free_transfers: int
    ) -> List[TransferOption]:
        """Select best transfers within constraints."""
        
        if not transfer_options:
            return []
            
        # Simple greedy selection - take highest gain transfers
        selected = []
        used_players_out = set()
        used_players_in = set()
        
        for option in transfer_options:
            if len(selected) >= max_transfers:
                break
                
            # Check if players are already involved in other transfers
            if (option.player_out_id in used_players_out or 
                option.player_in_id in used_players_in):
                continue
                
            # Check if transfer is profitable considering cost
            transfer_cost = 4 if len(selected) >= free_transfers else 0
            if option.expected_gain > transfer_cost:
                selected.append(option)
                used_players_out.add(option.player_out_id)
                used_players_in.add(option.player_in_id)
                
        return selected
        
    def _apply_transfers(
        self,
        current_squad: List[PlayerData],
        transfers: List[TransferOption]
    ) -> List[PlayerData]:
        """Apply transfers to get new squad."""
        
        new_squad = current_squad.copy()
        
        # Remove players being transferred out
        players_out = {t.player_out_id for t in transfers}
        new_squad = [p for p in new_squad if p.id not in players_out]
        
        # Add players being transferred in
        # Note: In a full implementation, we'd need access to the full player database here
        # For now, we'll assume the new players are provided
        
        return new_squad
        
    def _calculate_squad_expected_points(self, squad: List[PlayerData]) -> float:
        """Calculate expected points for a squad."""
        
        # Simplified calculation - in reality would use optimizer
        total_points = 0.0
        
        # Sort by predicted points to get best starting XI
        sorted_squad = sorted(squad, key=lambda p: p.predicted_points, reverse=True)
        starting_xi = sorted_squad[:11]
        
        for player in starting_xi:
            total_points += player.predicted_points * player.start_probability
            
        # Add captain bonus for best player
        if starting_xi:
            best_captain = max(starting_xi, key=lambda p: p.predicted_points * p.start_probability)
            total_points += best_captain.predicted_points * best_captain.start_probability
            
        return total_points
        
    def _update_state(self, current_state: Dict[str, Any], week_plan: GameweekPlan) -> Dict[str, Any]:
        """Update state after applying week's plan."""
        
        # Apply transfers to squad
        new_squad = self._apply_transfers(current_state['squad'], week_plan.transfers)
        
        # Update free transfers (reset to 1, or 2 if no transfers made)
        new_free_transfers = 2 if not week_plan.transfers else 1
        
        return {
            'squad': new_squad,
            'gameweek': week_plan.gameweek + 1,
            'free_transfers': new_free_transfers,
            'squad_value': week_plan.squad_value,
            'chips_used': current_state['chips_used'].copy()
        }
        
    def _analyze_chip_usage(
        self,
        gameweek_plans: List[GameweekPlan],
        available_chips: Dict[str, bool],
        current_gameweek: int,
        planning_horizon: int
    ) -> Dict[str, ChipStrategy]:
        """Analyze optimal chip usage timing."""
        
        chip_strategies = {}
        
        # Triple Captain analysis
        if available_chips.get('triple_captain', False):
            best_tc_gw = self._find_best_triple_captain_gameweek(
                gameweek_plans, current_gameweek
            )
            chip_strategies['triple_captain'] = best_tc_gw
            
        # Bench Boost analysis
        if available_chips.get('bench_boost', False):
            best_bb_gw = self._find_best_bench_boost_gameweek(
                gameweek_plans, current_gameweek
            )
            chip_strategies['bench_boost'] = best_bb_gw
            
        # Wildcard analysis
        if available_chips.get('wildcard', False):
            wildcard_strategy = self._analyze_wildcard_timing(
                gameweek_plans, current_gameweek, planning_horizon
            )
            chip_strategies['wildcard'] = wildcard_strategy
            
        # Free Hit analysis
        if available_chips.get('free_hit', False):
            free_hit_strategy = self._analyze_free_hit_timing(
                gameweek_plans, current_gameweek
            )
            chip_strategies['free_hit'] = free_hit_strategy
            
        return chip_strategies
        
    def _find_best_triple_captain_gameweek(
        self,
        gameweek_plans: List[GameweekPlan],
        current_gameweek: int
    ) -> ChipStrategy:
        """Find best gameweek for Triple Captain chip."""
        
        best_gameweek = None
        best_benefit = 0.0
        
        for plan in gameweek_plans:
            # Find best captain option for this gameweek
            # Simplified - in reality would analyze squad composition
            expected_captain_points = 12.0  # Placeholder
            triple_captain_benefit = expected_captain_points  # Extra points from TC
            
            if triple_captain_benefit > best_benefit:
                best_benefit = triple_captain_benefit
                best_gameweek = plan.gameweek
                
        return ChipStrategy(
            chip_type='triple_captain',
            recommended_gameweek=best_gameweek,
            expected_benefit=best_benefit,
            confidence=0.8
        )
        
    def _find_best_bench_boost_gameweek(
        self,
        gameweek_plans: List[GameweekPlan],
        current_gameweek: int
    ) -> ChipStrategy:
        """Find best gameweek for Bench Boost chip."""
        
        # Simplified implementation
        # In reality, would analyze when bench players are most likely to score
        
        return ChipStrategy(
            chip_type='bench_boost',
            recommended_gameweek=current_gameweek + 2,  # Placeholder
            expected_benefit=8.0,  # Expected bench points
            confidence=0.6
        )
        
    def _analyze_wildcard_timing(
        self,
        gameweek_plans: List[GameweekPlan],
        current_gameweek: int,
        planning_horizon: int
    ) -> ChipStrategy:
        """Analyze when to use Wildcard chip."""
        
        # Wildcard most beneficial when many transfers needed
        total_transfers_needed = sum(len(plan.transfers) for plan in gameweek_plans)
        
        if total_transfers_needed > planning_horizon * 2:
            # Many transfers needed - wildcard beneficial
            return ChipStrategy(
                chip_type='wildcard',
                recommended_gameweek=current_gameweek + 1,
                expected_benefit=total_transfers_needed * 4 - 4,  # Save transfer costs
                confidence=0.9
            )
        else:
            return ChipStrategy(
                chip_type='wildcard',
                recommended_gameweek=None,
                expected_benefit=0.0,
                confidence=0.3
            )
            
    def _analyze_free_hit_timing(
        self,
        gameweek_plans: List[GameweekPlan],
        current_gameweek: int
    ) -> ChipStrategy:
        """Analyze when to use Free Hit chip."""
        
        # Free Hit best for blank/double gameweeks or when team badly hit by injuries
        # Simplified implementation
        
        return ChipStrategy(
            chip_type='free_hit',
            recommended_gameweek=None,  # Need more context for this
            expected_benefit=0.0,
            confidence=0.5
        )
        
    def _gameweek_plan_to_dict(self, plan: GameweekPlan) -> Dict[str, Any]:
        """Convert GameweekPlan to dictionary."""
        
        return {
            'gameweek': plan.gameweek,
            'transfers': [self._transfer_to_dict(t) for t in plan.transfers],
            'expected_points': round(plan.expected_points, 1),
            'squad_value': round(plan.squad_value, 1),
            'free_transfers': plan.free_transfers,
            'total_transfer_cost': plan.total_transfer_cost,
            'net_expected_gain': round(plan.expected_points - plan.total_transfer_cost, 1)
        }
        
    def _transfer_to_dict(self, transfer: TransferOption) -> Dict[str, Any]:
        """Convert TransferOption to dictionary."""
        
        return {
            'player_out_id': transfer.player_out_id,
            'player_in_id': transfer.player_in_id,
            'cost': transfer.cost,
            'expected_gain': round(transfer.expected_gain, 1),
            'price_change': round(transfer.price_change, 1),
            'gameweek': transfer.gameweek
        }
        
    def analyze_fixture_swings(
        self,
        all_players: List[PlayerData],
        fixture_difficulties: Dict[int, List[int]],  # team_id -> list of difficulties
        current_gameweek: int,
        horizon: int = 6
    ) -> Dict[str, Any]:
        """Analyze fixture difficulty swings for transfer planning."""
        
        logger.info(f"Analyzing fixture swings for next {horizon} gameweeks")
        
        fixture_analysis = {}
        
        # Group players by team
        players_by_team = {}
        for player in all_players:
            if player.team_id not in players_by_team:
                players_by_team[player.team_id] = []
            players_by_team[player.team_id].append(player)
            
        for team_id, team_players in players_by_team.items():
            if team_id not in fixture_difficulties:
                continue
                
            team_fixtures = fixture_difficulties[team_id]
            
            # Calculate fixture swing score
            # Lower scores = easier fixtures ahead
            avg_difficulty = np.mean(team_fixtures[:horizon])
            difficulty_trend = np.mean(team_fixtures[horizon//2:]) - np.mean(team_fixtures[:horizon//2])
            
            fixture_analysis[team_id] = {
                'team_id': team_id,
                'avg_difficulty': round(avg_difficulty, 2),
                'difficulty_trend': round(difficulty_trend, 2),  # Negative = getting easier
                'fixtures': team_fixtures[:horizon],
                'top_players': [
                    {
                        'player_id': p.id,
                        'name': p.name,
                        'position': p.position,
                        'predicted_points': p.predicted_points,
                        'price': p.price
                    }
                    for p in sorted(team_players, key=lambda x: x.predicted_points, reverse=True)[:3]
                ]
            }
            
        # Sort teams by fixture attractiveness (lower difficulty + improving trend)
        fixture_ranking = sorted(
            fixture_analysis.values(),
            key=lambda x: x['avg_difficulty'] - x['difficulty_trend']
        )
        
        return {
            'best_fixtures': fixture_ranking[:5],
            'worst_fixtures': fixture_ranking[-5:],
            'all_teams': fixture_analysis,
            'gameweek_range': f"{current_gameweek}-{current_gameweek + horizon - 1}"
        }