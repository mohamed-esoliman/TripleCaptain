"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create teams table
    op.create_table('teams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fpl_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('short_name', sa.String(), nullable=False),
        sa.Column('code', sa.Integer(), nullable=True),
        sa.Column('strength', sa.Integer(), nullable=True),
        sa.Column('strength_overall_home', sa.Integer(), nullable=True),
        sa.Column('strength_overall_away', sa.Integer(), nullable=True),
        sa.Column('strength_attack_home', sa.Integer(), nullable=True),
        sa.Column('strength_attack_away', sa.Integer(), nullable=True),
        sa.Column('strength_defence_home', sa.Integer(), nullable=True),
        sa.Column('strength_defence_away', sa.Integer(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=True),
        sa.Column('played', sa.Integer(), nullable=True, default=0),
        sa.Column('won', sa.Integer(), nullable=True, default=0),
        sa.Column('drawn', sa.Integer(), nullable=True, default=0),
        sa.Column('lost', sa.Integer(), nullable=True, default=0),
        sa.Column('points', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_teams_fpl_id', 'teams', ['fpl_id'], unique=True)
    op.create_index('ix_teams_id', 'teams', ['id'])

    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('fpl_team_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # Create players table
    op.create_table('players',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fpl_id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('second_name', sa.String(), nullable=False),
        sa.Column('web_name', sa.String(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('current_price', sa.Integer(), nullable=False),
        sa.Column('total_points', sa.Integer(), nullable=True, default=0),
        sa.Column('form', sa.Float(), nullable=True, default=0.0),
        sa.Column('status', sa.String(), nullable=True, default='a'),
        sa.Column('chance_playing_this', sa.Integer(), nullable=True),
        sa.Column('chance_playing_next', sa.Integer(), nullable=True),
        sa.Column('selected_by_percent', sa.Float(), nullable=True, default=0.0),
        sa.Column('transfers_in_event', sa.Integer(), nullable=True, default=0),
        sa.Column('transfers_out_event', sa.Integer(), nullable=True, default=0),
        sa.Column('goals_scored', sa.Integer(), nullable=True, default=0),
        sa.Column('assists', sa.Integer(), nullable=True, default=0),
        sa.Column('clean_sheets', sa.Integer(), nullable=True, default=0),
        sa.Column('goals_conceded', sa.Integer(), nullable=True, default=0),
        sa.Column('yellow_cards', sa.Integer(), nullable=True, default=0),
        sa.Column('red_cards', sa.Integer(), nullable=True, default=0),
        sa.Column('saves', sa.Integer(), nullable=True, default=0),
        sa.Column('bonus', sa.Integer(), nullable=True, default=0),
        sa.Column('bps', sa.Integer(), nullable=True, default=0),
        sa.Column('influence', sa.Float(), nullable=True, default=0.0),
        sa.Column('creativity', sa.Float(), nullable=True, default=0.0),
        sa.Column('threat', sa.Float(), nullable=True, default=0.0),
        sa.Column('ict_index', sa.Float(), nullable=True, default=0.0),
        sa.Column('ep_this', sa.Float(), nullable=True, default=0.0),
        sa.Column('ep_next', sa.Float(), nullable=True, default=0.0),
        sa.Column('cost_change_event', sa.Integer(), nullable=True, default=0),
        sa.Column('cost_change_start', sa.Integer(), nullable=True, default=0),
        sa.Column('news', sa.Text(), nullable=True),
        sa.Column('news_added', sa.DateTime(timezone=True), nullable=True),
        sa.Column('photo', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_player_position', 'players', ['position'])
    op.create_index('idx_player_price', 'players', ['current_price'])
    op.create_index('idx_player_status', 'players', ['status'])
    op.create_index('idx_player_team', 'players', ['team_id'])
    op.create_index('ix_players_fpl_id', 'players', ['fpl_id'], unique=True)
    op.create_index('ix_players_id', 'players', ['id'])

    # Create fixtures table
    op.create_table('fixtures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fpl_id', sa.Integer(), nullable=False),
        sa.Column('gameweek', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('team_h_id', sa.Integer(), nullable=False),
        sa.Column('team_a_id', sa.Integer(), nullable=False),
        sa.Column('team_h_score', sa.Integer(), nullable=True),
        sa.Column('team_a_score', sa.Integer(), nullable=True),
        sa.Column('team_h_difficulty', sa.Integer(), nullable=True),
        sa.Column('team_a_difficulty', sa.Integer(), nullable=True),
        sa.Column('kickoff_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished', sa.Boolean(), nullable=True, default=False),
        sa.Column('finished_provisional', sa.Boolean(), nullable=True, default=False),
        sa.Column('started', sa.Boolean(), nullable=True, default=False),
        sa.Column('minutes', sa.Integer(), nullable=True, default=0),
        sa.Column('provisional_start_time', sa.Boolean(), nullable=True, default=False),
        sa.Column('pulse_id', sa.Integer(), nullable=True),
        sa.Column('stats', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['team_a_id'], ['teams.id'], ),
        sa.ForeignKeyConstraint(['team_h_id'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_fixture_gameweek', 'fixtures', ['gameweek'])
    op.create_index('idx_fixture_kickoff', 'fixtures', ['kickoff_time'])
    op.create_index('idx_fixture_teams', 'fixtures', ['team_h_id', 'team_a_id'])
    op.create_index('ix_fixtures_fpl_id', 'fixtures', ['fpl_id'], unique=True)
    op.create_index('ix_fixtures_id', 'fixtures', ['id'])

    # Create player_statistics table
    op.create_table('player_statistics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('gameweek', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('fixture_id', sa.Integer(), nullable=True),
        sa.Column('opponent_team_id', sa.Integer(), nullable=True),
        sa.Column('was_home', sa.Boolean(), nullable=True),
        sa.Column('minutes', sa.Integer(), nullable=True, default=0),
        sa.Column('goals_scored', sa.Integer(), nullable=True, default=0),
        sa.Column('assists', sa.Integer(), nullable=True, default=0),
        sa.Column('clean_sheets', sa.Integer(), nullable=True, default=0),
        sa.Column('goals_conceded', sa.Integer(), nullable=True, default=0),
        sa.Column('own_goals', sa.Integer(), nullable=True, default=0),
        sa.Column('penalties_saved', sa.Integer(), nullable=True, default=0),
        sa.Column('penalties_missed', sa.Integer(), nullable=True, default=0),
        sa.Column('yellow_cards', sa.Integer(), nullable=True, default=0),
        sa.Column('red_cards', sa.Integer(), nullable=True, default=0),
        sa.Column('saves', sa.Integer(), nullable=True, default=0),
        sa.Column('bonus', sa.Integer(), nullable=True, default=0),
        sa.Column('bps', sa.Integer(), nullable=True, default=0),
        sa.Column('influence', sa.Float(), nullable=True, default=0.0),
        sa.Column('creativity', sa.Float(), nullable=True, default=0.0),
        sa.Column('threat', sa.Float(), nullable=True, default=0.0),
        sa.Column('ict_index', sa.Float(), nullable=True, default=0.0),
        sa.Column('total_points', sa.Integer(), nullable=True, default=0),
        sa.Column('starts', sa.Integer(), nullable=True, default=0),
        sa.Column('expected_goals', sa.Float(), nullable=True, default=0.0),
        sa.Column('expected_assists', sa.Float(), nullable=True, default=0.0),
        sa.Column('expected_goal_involvements', sa.Float(), nullable=True, default=0.0),
        sa.Column('expected_goals_conceded', sa.Float(), nullable=True, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['fixture_id'], ['fixtures.id'], ),
        sa.ForeignKeyConstraint(['opponent_team_id'], ['teams.id'], ),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_gameweek_season', 'player_statistics', ['gameweek', 'season'])
    op.create_index('idx_player_gameweek', 'player_statistics', ['player_id', 'gameweek'])
    op.create_index('idx_season', 'player_statistics', ['season'])
    op.create_index('ix_player_statistics_id', 'player_statistics', ['id'])

    # Create ml_predictions table
    op.create_table('ml_predictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('gameweek', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('predicted_points', sa.Float(), nullable=False),
        sa.Column('confidence_lower', sa.Float(), nullable=True),
        sa.Column('confidence_upper', sa.Float(), nullable=True),
        sa.Column('start_probability', sa.Float(), nullable=True, default=0.5),
        sa.Column('predicted_minutes', sa.Float(), nullable=True, default=0.0),
        sa.Column('ceiling_points', sa.Float(), nullable=True),
        sa.Column('floor_points', sa.Float(), nullable=True),
        sa.Column('variance', sa.Float(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_prediction_gameweek', 'ml_predictions', ['gameweek', 'season'])
    op.create_index('idx_prediction_player_gw', 'ml_predictions', ['player_id', 'gameweek'])
    op.create_index('idx_prediction_points', 'ml_predictions', ['predicted_points'])
    op.create_index('ix_ml_predictions_id', 'ml_predictions', ['id'])

    # Create refresh_tokens table
    op.create_table('refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_refresh_token', 'refresh_tokens', ['token'])
    op.create_index('idx_refresh_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_id', 'refresh_tokens', ['id'])
    op.create_index('ix_refresh_tokens_token', 'refresh_tokens', ['token'], unique=True)

    # Create user_squads table
    op.create_table('user_squads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gameweek', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('squad_data', sa.JSON(), nullable=False),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('predicted_points', sa.Float(), nullable=True),
        sa.Column('formation', sa.String(), nullable=True),
        sa.Column('captain_id', sa.Integer(), nullable=True),
        sa.Column('vice_captain_id', sa.Integer(), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['captain_id'], ['players.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vice_captain_id'], ['players.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_current', 'user_squads', ['user_id', 'is_current'])
    op.create_index('idx_user_gameweek', 'user_squads', ['user_id', 'gameweek'])
    op.create_index('ix_user_squads_id', 'user_squads', ['id'])

    # Create optimization_cache table
    op.create_table('optimization_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cache_key', sa.String(), nullable=False),
        sa.Column('gameweek', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(), nullable=False),
        sa.Column('constraints', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('predicted_points', sa.Float(), nullable=True),
        sa.Column('formation', sa.String(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_cache_expires', 'optimization_cache', ['expires_at'])
    op.create_index('idx_cache_gameweek', 'optimization_cache', ['gameweek', 'season'])
    op.create_index('ix_optimization_cache_cache_key', 'optimization_cache', ['cache_key'], unique=True)
    op.create_index('ix_optimization_cache_id', 'optimization_cache', ['id'])

    # Create data_update_logs table
    op.create_table('data_update_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('update_type', sa.String(), nullable=False),
        sa.Column('gameweek', sa.Integer(), nullable=True),
        sa.Column('season', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('records_processed', sa.Integer(), nullable=True, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_update_started', 'data_update_logs', ['started_at'])
    op.create_index('idx_update_type_status', 'data_update_logs', ['update_type', 'status'])
    op.create_index('ix_data_update_logs_id', 'data_update_logs', ['id'])


def downgrade() -> None:
    op.drop_table('data_update_logs')
    op.drop_table('optimization_cache')
    op.drop_table('user_squads')
    op.drop_table('refresh_tokens')
    op.drop_table('ml_predictions')
    op.drop_table('player_statistics')
    op.drop_table('fixtures')
    op.drop_table('players')
    op.drop_table('users')
    op.drop_table('teams')