import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { 
  AuthTokens, 
  LoginCredentials, 
  RegisterData, 
  User,
  Player,
  Team,
  Fixture,
  MLPrediction,
  OptimizationRequest,
  OptimizationResult,
  TransferPlanRequest,
  TransferPlanResult,
  PlayerFilters,
  PlayersResponse,
  ApiError,
  TeamSummary
} from '../types';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class APIClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Load tokens from localStorage
    this.loadTokensFromStorage();

    // Request interceptor to add auth token
    this.client.interceptors.request.use((config) => {
      if (this.accessToken) {
        config.headers.Authorization = `Bearer ${this.accessToken}`;
      }
      return config;
    });

    // Response interceptor to handle token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401 && this.refreshToken) {
          try {
            await this.refreshAccessToken();
            // Retry the original request
            return this.client(error.config);
          } catch (refreshError) {
            // Refresh failed, redirect to login
            this.clearTokens();
            window.location.href = '/login';
            throw refreshError;
          }
        }
        throw error;
      }
    );
  }

  private loadTokensFromStorage() {
    this.accessToken = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
  }

  private saveTokensToStorage(tokens: AuthTokens) {
    localStorage.setItem('access_token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);
    this.accessToken = tokens.access_token;
    this.refreshToken = tokens.refresh_token;
  }

  private clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    this.accessToken = null;
    this.refreshToken = null;
  }

  // Authentication Methods
  async login(credentials: LoginCredentials): Promise<User> {
    const response = await this.client.post<AuthTokens>('/api/v1/auth/login', credentials);
    this.saveTokensToStorage(response.data);
    
    // Get user info after successful login
    const userResponse = await this.client.get<User>('/api/v1/auth/me');
    return userResponse.data;
  }

  async register(userData: RegisterData): Promise<User> {
    const response = await this.client.post<User>('/api/v1/auth/register', userData);
    return response.data;
  }

  async logout(): Promise<void> {
    if (this.refreshToken) {
      try {
        await this.client.post('/api/v1/auth/logout', {
          refresh_token: this.refreshToken,
        });
      } catch (error) {
        // Ignore logout errors
        console.warn('Logout request failed:', error);
      }
    }
    this.clearTokens();
  }

  async refreshAccessToken(): Promise<void> {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await this.client.post<AuthTokens>('/api/v1/auth/refresh', {
      refresh_token: this.refreshToken,
    });

    this.saveTokensToStorage(response.data);
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<User>('/api/v1/auth/me');
    return response.data;
  }

  async updateCurrentUser(patch: Partial<User> & { fpl_team_id?: number }): Promise<User> {
    const response = await this.client.patch<User>('/api/v1/auth/me', patch);
    return response.data;
  }

  // Player Methods
  async getPlayers(filters?: PlayerFilters, page = 1, pageSize = 50): Promise<PlayersResponse> {
    const params = new URLSearchParams();
    
    if (filters?.position) params.append('position', filters.position.toString());
    if (filters?.team_id) params.append('team', filters.team_id.toString());
    if (filters?.min_price) params.append('min_price', filters.min_price.toString());
    if (filters?.max_price) params.append('max_price', filters.max_price.toString());
    if (filters?.min_points) params.append('min_points', filters.min_points.toString());
    if (filters?.status) params.append('status', filters.status);
    if (filters?.available_only !== undefined) params.append('available_only', filters.available_only.toString());
    
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());

    const response = await this.client.get<PlayersResponse>(`/api/v1/players?${params}`);
    return response.data;
  }

  async getPlayer(playerId: number): Promise<Player> {
    const response = await this.client.get<Player>(`/api/v1/players/${playerId}`);
    return response.data;
  }

  async getPlayerFixtures(playerId: number, limit = 5): Promise<any[]> {
    const response = await this.client.get<any[]>(`/api/v1/players/${playerId}/fixtures?limit=${limit}`);
    return response.data;
  }

  // Team Methods
  async getTeams(): Promise<Team[]> {
    const response = await this.client.get<Team[]>('/api/v1/teams');
    return response.data;
  }

  async getTeam(teamId: number): Promise<Team> {
    const response = await this.client.get<Team>(`/api/v1/teams/${teamId}`);
    return response.data;
  }

  // Fixture Methods
  async getFixtures(gameweek?: number): Promise<Fixture[]> {
    const params = gameweek ? `?gameweek=${gameweek}` : '';
    const response = await this.client.get<Fixture[]>(`/api/v1/fixtures${params}`);
    return response.data;
  }

  // Prediction Methods
  async getPredictions(gameweek: number, playerIds?: number[]): Promise<MLPrediction[]> {
    const params = new URLSearchParams({ gameweek: gameweek.toString() });
    if (playerIds?.length) {
      playerIds.forEach(id => params.append('player_ids', id.toString()));
    }
    
    const response = await this.client.get<MLPrediction[]>(`/api/v1/predictions?${params}`);
    return response.data;
  }

  async getPlayerPrediction(playerId: number, gameweek: number): Promise<MLPrediction> {
    const response = await this.client.get<MLPrediction>(`/api/v1/predictions/player/${playerId}/${gameweek}`);
    return response.data;
  }

  // Optimization Methods
  async optimizeSquad(request: OptimizationRequest): Promise<OptimizationResult> {
    const response = await this.client.post<OptimizationResult>('/api/v1/optimization/squad', request);
    return response.data;
  }

  async quickPick(gameweek: number, formation = '3-4-3', risk = 0.5): Promise<OptimizationResult & { explanation?: any }> {
    const response = await this.client.post<OptimizationResult & { explanation?: any }>(`/api/v1/optimization/quick-pick/${gameweek}?formation=${encodeURIComponent(formation)}&risk_tolerance=${risk}`);
    return response.data;
  }

  async optimizeFormation(playerIds: number[], gameweek: number): Promise<OptimizationResult> {
    const request = {
      gameweek,
      required_players: playerIds,
    };
    const response = await this.client.post<OptimizationResult>('/api/v1/optimization/formation', request);
    return response.data;
  }

  async optimizeCaptain(playerIds: number[]): Promise<any> {
    const response = await this.client.post('/api/v1/optimization/captain', { player_ids: playerIds });
    return response.data;
  }

  // Transfer Planning Methods
  async planTransfers(request: TransferPlanRequest): Promise<TransferPlanResult> {
    const response = await this.client.post<TransferPlanResult>('/api/v1/optimization/transfers', request);
    return response.data;
  }

  // Squad Management Methods
  async getCurrentSquad(): Promise<any> {
    const response = await this.client.get('/api/v1/squads/current');
    return response.data;
  }

  async saveSquad(squadData: any): Promise<any> {
    const response = await this.client.post('/api/v1/squads/save', squadData);
    return response.data;
  }

  // Team Summary
  async getTeamSummary(entryId?: number): Promise<TeamSummary> {
    const url = entryId ? `/api/v1/team/summary?entry_id=${entryId}` : '/api/v1/team/summary';
    const response = await this.client.get<TeamSummary>(url);
    return response.data;
  }

  async getSquadHistory(): Promise<any[]> {
    const response = await this.client.get('/api/v1/squads/history');
    return response.data;
  }

  async importSquadFromFPL(entryId: number): Promise<any> {
    const response = await this.client.post('/api/v1/squads/import-from-fpl', { entry_id: entryId });
    return response.data;
  }

  // Analytics Methods
  async getUserPerformance(): Promise<any> {
    const response = await this.client.get('/api/v1/analytics/performance');
    return response.data;
  }

  async getMarketTrends(): Promise<any> {
    const response = await this.client.get('/api/v1/analytics/trends');
    return response.data;
  }

  async getFixtureDifficulty(): Promise<any> {
    const response = await this.client.get('/api/v1/analytics/fixtures');
    return response.data;
  }

  // Utility Methods
  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  // Admin & Maintenance Methods
  async runAdminTask(
    taskName: 'data_sync' | 'generate_predictions' | 'train_models' | 'clear_cache',
    params?: { gameweek?: number; pattern?: string }
  ): Promise<any> {
    const body: Record<string, any> = {};
    if (params?.gameweek !== undefined) body.gameweek = params.gameweek;
    if (params?.pattern !== undefined) body.pattern = params.pattern;
    const response = await this.client.post(`/api/v1/admin/tasks/${taskName}`, body);
    return response.data;
  }

  async getAdminCacheStats(): Promise<any> {
    const response = await this.client.get('/api/v1/admin/cache/stats');
    return response.data;
  }

  async clearCache(pattern = '*'): Promise<any> {
    const response = await this.client.delete('/api/v1/admin/cache', { params: { pattern } });
    return response.data;
  }

  async getAdminHealth(): Promise<any> {
    const response = await this.client.get('/api/v1/admin/health');
    return response.data;
  }

  async getSystemStats(): Promise<any> {
    const response = await this.client.get('/api/v1/admin/stats');
    return response.data;
  }
}

// Create singleton instance
const apiClient = new APIClient();

export default apiClient;