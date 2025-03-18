import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import logging

from app.db.models import Player, PlayerStatistic, Team, Fixture
from app.services.fpl_client import get_season_string

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Feature engineering for ML predictions."""
    
    def __init__(self):
        self.season = get_season_string()
        
    async def get_player_features(
        self, 
        db: AsyncSession, 
        player_id: int, 
        target_gameweek: int,
        lookback_weeks: int = 10
    ) -> Dict[str, float]:
        """Generate comprehensive features for a player."""
        
        # Get player basic info
        player_result = await db.execute(
            select(Player, Team)
            .join(Team, Player.team_id == Team.id)
            .where(Player.id == player_id)
        )
        player_row = player_result.first()
        
        if not player_row:
            raise ValueError(f"Player {player_id} not found")
            
        player, team = player_row
        
        # Get historical statistics
        stats_query = select(PlayerStatistic).where(
            PlayerStatistic.player_id == player_id,
            PlayerStatistic.season == self.season,
            PlayerStatistic.gameweek < target_gameweek,
            PlayerStatistic.gameweek >= max(1, target_gameweek - lookback_weeks)
        ).order_by(PlayerStatistic.gameweek.desc())
        
        stats_result = await db.execute(stats_query)
        recent_stats = stats_result.scalars().all()
        
        # Convert to DataFrame for easier manipulation
        if recent_stats:
            stats_df = pd.DataFrame([{
                'gameweek': stat.gameweek,
                'minutes': stat.minutes,
                'total_points': stat.total_points,
                'goals_scored': stat.goals_scored,
                'assists': stat.assists,
                'clean_sheets': stat.clean_sheets,
                'goals_conceded': stat.goals_conceded,
                'yellow_cards': stat.yellow_cards,
                'red_cards': stat.red_cards,
                'saves': stat.saves,
                'bonus': stat.bonus,
                'bps': stat.bps,
                'influence': float(stat.influence),
                'creativity': float(stat.creativity),
                'threat': float(stat.threat),
                'ict_index': float(stat.ict_index),
                'expected_goals': float(stat.expected_goals),
                'expected_assists': float(stat.expected_assists),
                'was_home': stat.was_home,
                'starts': stat.starts
            } for stat in recent_stats])
        else:
            stats_df = pd.DataFrame()
            
        # Generate features
        features = {}
        
        # Basic player features
        features.update(self._get_basic_player_features(player, team))
        
        # Form and consistency features
        features.update(self._get_form_features(stats_df))
        
        # Performance rate features
        features.update(self._get_performance_rate_features(stats_df))
        
        # Fixture context features
        fixture_features = await self._get_fixture_features(
            db, player.team_id, target_gameweek
        )
        features.update(fixture_features)
        
        # Team strength features
        features.update(self._get_team_strength_features(team))
        
        # Seasonal timing features
        features.update(self._get_seasonal_features(target_gameweek))
        
        # Advanced metrics
        features.update(self._get_advanced_metrics(stats_df))
        
        return features
        
    def _get_basic_player_features(self, player: Player, team: Team) -> Dict[str, float]:
        """Extract basic player and team features."""
        return {
            'position': float(player.position),
            'price': float(player.current_price / 10.0),  # Convert to millions
            'total_points': float(player.total_points),
            'form': float(player.form),
            'selected_by_percent': float(player.selected_by_percent),
            'transfers_in_event': float(player.transfers_in_event),
            'transfers_out_event': float(player.transfers_out_event),
            'cost_change_start': float(player.cost_change_start),
            'team_strength': float(team.strength or 0),
            'ep_this': float(player.ep_this),
            'ep_next': float(player.ep_next),
            'chance_playing_this': float(player.chance_playing_this or 75),
            'is_available': 1.0 if player.status == 'a' else 0.0
        }
        
    def _get_form_features(self, stats_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate form-related features."""
        if stats_df.empty:
            return {
                'points_last_3': 0.0,
                'points_last_5': 0.0,
                'points_last_10': 0.0,
                'avg_points_last_3': 0.0,
                'avg_points_last_5': 0.0,
                'avg_minutes_last_5': 0.0,
                'games_started_last_5': 0.0,
                'form_trend': 0.0,
                'consistency_score': 0.0
            }
            
        # Rolling sums and averages
        points_last_3 = stats_df.head(3)['total_points'].sum()
        points_last_5 = stats_df.head(5)['total_points'].sum()
        points_last_10 = stats_df.head(10)['total_points'].sum()
        
        avg_points_last_3 = stats_df.head(3)['total_points'].mean()
        avg_points_last_5 = stats_df.head(5)['total_points'].mean()
        avg_minutes_last_5 = stats_df.head(5)['minutes'].mean()
        
        # Starting frequency
        games_started_last_5 = stats_df.head(5)['starts'].sum()
        
        # Form trend (linear regression slope)
        if len(stats_df) >= 3:
            x = np.arange(len(stats_df))
            y = stats_df['total_points'].values[::-1]  # Reverse for chronological order
            form_trend = np.polyfit(x, y, 1)[0] if len(y) > 1 else 0.0
        else:
            form_trend = 0.0
            
        # Consistency (inverse of standard deviation)
        consistency_score = 1.0 / (stats_df['total_points'].std() + 1.0)
        
        return {
            'points_last_3': float(points_last_3),
            'points_last_5': float(points_last_5),
            'points_last_10': float(points_last_10),
            'avg_points_last_3': float(avg_points_last_3),
            'avg_points_last_5': float(avg_points_last_5),
            'avg_minutes_last_5': float(avg_minutes_last_5),
            'games_started_last_5': float(games_started_last_5),
            'form_trend': float(form_trend),
            'consistency_score': float(consistency_score)
        }
        
    def _get_performance_rate_features(self, stats_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate per-90-minute performance rates."""
        if stats_df.empty:
            return {
                'goals_per_90': 0.0,
                'assists_per_90': 0.0,
                'points_per_90': 0.0,
                'bonus_per_90': 0.0,
                'cards_per_90': 0.0,
                'saves_per_90': 0.0,
                'clean_sheet_rate': 0.0,
                'blank_rate': 0.0
            }
            
        # Filter games where player actually played
        played_df = stats_df[stats_df['minutes'] > 0].copy()
        
        if played_df.empty:
            return {
                'goals_per_90': 0.0,
                'assists_per_90': 0.0,
                'points_per_90': 0.0,
                'bonus_per_90': 0.0,
                'cards_per_90': 0.0,
                'saves_per_90': 0.0,
                'clean_sheet_rate': 0.0,
                'blank_rate': 0.0
            }
            
        total_minutes = played_df['minutes'].sum()
        
        if total_minutes == 0:
            return {
                'goals_per_90': 0.0,
                'assists_per_90': 0.0,
                'points_per_90': 0.0,
                'bonus_per_90': 0.0,
                'cards_per_90': 0.0,
                'saves_per_90': 0.0,
                'clean_sheet_rate': 0.0,
                'blank_rate': 0.0
            }
        
        return {
            'goals_per_90': float(played_df['goals_scored'].sum() * 90 / total_minutes),
            'assists_per_90': float(played_df['assists'].sum() * 90 / total_minutes),
            'points_per_90': float(played_df['total_points'].sum() * 90 / total_minutes),
            'bonus_per_90': float(played_df['bonus'].sum() * 90 / total_minutes),
            'cards_per_90': float((played_df['yellow_cards'].sum() + played_df['red_cards'].sum() * 2) * 90 / total_minutes),
            'saves_per_90': float(played_df['saves'].sum() * 90 / total_minutes),
            'clean_sheet_rate': float(played_df['clean_sheets'].mean()),
            'blank_rate': float((played_df['total_points'] == 0).mean())
        }
        
    async def _get_fixture_features(
        self, 
        db: AsyncSession, 
        team_id: int, 
        target_gameweek: int
    ) -> Dict[str, float]:
        """Get fixture context features."""
        
        # Get next fixture
        fixture_query = select(Fixture, Team.strength_defence_home, Team.strength_defence_away).join(
            Team, 
            (Fixture.team_h_id == Team.id) | (Fixture.team_a_id == Team.id)
        ).where(
            ((Fixture.team_h_id == team_id) | (Fixture.team_a_id == team_id)),
            Fixture.gameweek == target_gameweek,
            Fixture.season == self.season
        )
        
        fixture_result = await db.execute(fixture_query)
        fixture_row = fixture_result.first()
        
        if not fixture_row:
            return {
                'is_home': 0.0,
                'opponent_strength': 3.0,  # Average strength
                'fixture_difficulty': 3.0,
                'days_since_last_game': 7.0
            }
            
        fixture = fixture_row[0]
        is_home = fixture.team_h_id == team_id
        
        # Get opponent strength
        if is_home:
            opponent_strength = fixture.away_team.strength if fixture.away_team else 3.0
            fixture_difficulty = float(fixture.team_h_difficulty or 3.0)
        else:
            opponent_strength = fixture.home_team.strength if fixture.home_team else 3.0
            fixture_difficulty = float(fixture.team_a_difficulty or 3.0)
            
        # Calculate days since last game (simplified)
        days_since_last = 7.0  # Assume weekly games for now
        
        return {
            'is_home': 1.0 if is_home else 0.0,
            'opponent_strength': float(opponent_strength),
            'fixture_difficulty': fixture_difficulty,
            'days_since_last_game': days_since_last
        }
        
    def _get_team_strength_features(self, team: Team) -> Dict[str, float]:
        """Get team strength features."""
        return {
            'team_attack_home': float(team.strength_attack_home or 1000) / 1000.0,
            'team_attack_away': float(team.strength_attack_away or 1000) / 1000.0,
            'team_defence_home': float(team.strength_defence_home or 1000) / 1000.0,
            'team_defence_away': float(team.strength_defence_away or 1000) / 1000.0,
            'team_overall_home': float(team.strength_overall_home or 1000) / 1000.0,
            'team_overall_away': float(team.strength_overall_away or 1000) / 1000.0,
            'team_position': float(team.position or 10),
            'team_points': float(team.points or 0)
        }
        
    def _get_seasonal_features(self, gameweek: int) -> Dict[str, float]:
        """Get seasonal timing features."""
        return {
            'gameweek': float(gameweek),
            'season_progress': float(gameweek / 38.0),
            'is_early_season': 1.0 if gameweek <= 10 else 0.0,
            'is_mid_season': 1.0 if 10 < gameweek <= 28 else 0.0,
            'is_late_season': 1.0 if gameweek > 28 else 0.0
        }
        
    def _get_advanced_metrics(self, stats_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate advanced performance metrics."""
        if stats_df.empty:
            return {
                'avg_ict_index': 0.0,
                'avg_bps': 0.0,
                'avg_influence': 0.0,
                'avg_creativity': 0.0,
                'avg_threat': 0.0,
                'home_away_split': 0.0,
                'expected_goals_per_90': 0.0,
                'expected_assists_per_90': 0.0
            }
            
        played_df = stats_df[stats_df['minutes'] > 0].copy()
        
        if played_df.empty:
            return {
                'avg_ict_index': 0.0,
                'avg_bps': 0.0,
                'avg_influence': 0.0,
                'avg_creativity': 0.0,
                'avg_threat': 0.0,
                'home_away_split': 0.0,
                'expected_goals_per_90': 0.0,
                'expected_assists_per_90': 0.0
            }
            
        total_minutes = played_df['minutes'].sum()
        
        # Home/away performance split
        home_games = played_df[played_df['was_home'] == True]
        away_games = played_df[played_df['was_home'] == False]
        
        home_avg = home_games['total_points'].mean() if not home_games.empty else 0
        away_avg = away_games['total_points'].mean() if not away_games.empty else 0
        home_away_split = home_avg - away_avg
        
        return {
            'avg_ict_index': float(played_df['ict_index'].mean()),
            'avg_bps': float(played_df['bps'].mean()),
            'avg_influence': float(played_df['influence'].mean()),
            'avg_creativity': float(played_df['creativity'].mean()),
            'avg_threat': float(played_df['threat'].mean()),
            'home_away_split': float(home_away_split),
            'expected_goals_per_90': float(played_df['expected_goals'].sum() * 90 / total_minutes) if total_minutes > 0 else 0.0,
            'expected_assists_per_90': float(played_df['expected_assists'].sum() * 90 / total_minutes) if total_minutes > 0 else 0.0
        }
        
    async def get_all_player_features(
        self, 
        db: AsyncSession, 
        gameweek: int, 
        player_ids: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """Get features for all players (or specified list) for a gameweek."""
        
        # Get all active players if no specific list provided
        if player_ids is None:
            players_query = select(Player.id).where(Player.status.in_(['a', 'i']))
            result = await db.execute(players_query)
            player_ids = [row[0] for row in result.all()]
            
        logger.info(f"Generating features for {len(player_ids)} players for GW{gameweek}")
        
        features_list = []
        
        for i, player_id in enumerate(player_ids):
            if i % 50 == 0:
                logger.info(f"Processing player {i+1}/{len(player_ids)}")
                
            try:
                features = await self.get_player_features(db, player_id, gameweek)
                features['player_id'] = player_id
                features['gameweek'] = gameweek
                features_list.append(features)
                
            except Exception as e:
                logger.warning(f"Failed to generate features for player {player_id}: {e}")
                continue
                
        features_df = pd.DataFrame(features_list)
        logger.info(f"Generated features for {len(features_df)} players")
        
        return features_df