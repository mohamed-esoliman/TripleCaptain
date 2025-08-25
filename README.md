# TripleCaptain 🏆

A full-stack Fantasy Premier League optimization platform that uses machine learning to predict player performance and mathematical optimization to suggest optimal squad selections and transfer strategies.

![TripleCaptain Demo](docs/demo.png)

## 🚀 Quick Start

The fastest way to get started is using our setup script:

```bash
git clone <repo-url>
cd TripleCaptain
python setup.py
```

This will automatically:

- Check dependencies
- Install all requirements
- Set up databases
- Create environment files in `backend/.env` and `frontend/.env`
- Sync initial FPL data
- Start development servers

Alternatively, you can use the dev scripts:

```bash
# Start dev databases (Postgres + Redis) and servers
./scripts/start_dev.sh

# Stop all services
./scripts/stop_dev.sh
```

## 🛠 Technology Stack

### Backend

- **Framework:** Python FastAPI
- **Database:** PostgreSQL (primary data), Redis (caching & sessions)
- **ML Libraries:** scikit-learn, XGBoost, pandas, numpy
- **Optimization:** PuLP (Linear Programming), scipy
- **Authentication:** JWT with refresh tokens
- **Background Tasks:** AsyncIO-based task scheduler

### Frontend

- **Framework:** React 18+ with TypeScript
- **Styling:** Tailwind CSS with custom FPL theme
- **State Management:** React Context + TanStack React Query
- **HTTP Client:** Axios with automatic token refresh

### External APIs

- Official FPL API for player data and statistics
- Real-time updates with intelligent caching

## 🎯 Core Features

### 🤖 Machine Learning System

- **Ensemble Predictions:** XGBoost + Random Forest + Linear Regression
- **Feature Engineering:** 40+ advanced features including form, fixtures, team strength
- **Multiple Targets:** Points, minutes, ceiling/floor scenarios
- **Model Monitoring:** Automatic performance tracking and retraining

### ⚡ Optimization Engine

- **Mathematical Programming:** Mixed Integer Linear Programming with PuLP
- **Squad Selection:** Optimal 15-player squad with formation constraints
- **Transfer Planning:** Multi-gameweek strategy with chip optimization
- **Risk Management:** Portfolio theory for player correlation analysis

### 📊 Real-time Data Pipeline

- **FPL API Integration:** Automatic daily data synchronization
- **Background Tasks:** Scheduled updates and model retraining
- **Intelligent Caching:** Redis-based caching with smart invalidation
- **Rate Limiting:** Respectful API usage with exponential backoff

### 🔐 Authentication & Security

- **JWT Tokens:** Secure authentication with refresh token rotation
- **Password Security:** bcrypt hashing with salt
- **CORS Protection:** Configurable cross-origin requests
- **Input Validation:** Comprehensive request validation

## 🚀 Getting Started

### Method 1: Automated Setup (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd TripleCaptain

# Run the setup script (requires Python 3.9+ and Node.js 18+)
python setup.py

# The script will handle everything automatically!
```

### Method 2: Manual Setup

#### Prerequisites

- Python 3.9+
- Node.js 18+
- Docker (for databases)

#### 1. Start Database Services

```bash
docker-compose up -d
```

#### 2. Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables (a default `backend/.env` is auto-created by setup.py)
# If not using the setup script, create `backend/.env` with at least:
# DATABASE_URL=postgresql://postgres:password@localhost:5432/triplecaptain
# REDIS_URL=redis://localhost:6379
# JWT_SECRET=change-me

# Run database migrations
python -c "from app.db.database import sync_engine; from app.db.models import Base; Base.metadata.create_all(sync_engine)"

# Start the server
uvicorn app.main:app --reload
```

#### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment variables (a default `frontend/.env` is auto-created by setup.py)
# If not using the setup script, create `frontend/.env` with at least:
# REACT_APP_API_URL=http://localhost:8000

# Start development server
npm start
```

### 🌐 Access Points

Once running, you can access:

- **Frontend Application:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Database:** localhost:5432 (postgres/password)
- **Redis Cache:** localhost:6379

### 🔧 Configuration

- Backend configuration is read from `backend/.env` via `pydantic-settings`.
- Frontend configuration is read from `frontend/.env` (Create React App style `REACT_APP_*` vars).
- For production, set strong values for `JWT_SECRET` and restrict `ALLOWED_ORIGINS`.

### Manual Background Tasks

```bash
# Sync FPL data
curl -X POST "http://localhost:8000/api/v1/admin/tasks/data_sync" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# Generate predictions for gameweek
curl -X POST "http://localhost:8000/api/v1/admin/tasks/generate_predictions?gameweek=1" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# Train ML models
curl -X POST "http://localhost:8000/api/v1/admin/tasks/train_models" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# Clear cache keys (pattern supports wildcards)
curl -X POST "http://localhost:8000/api/v1/admin/tasks/clear_cache" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pattern":"players:*"}'
```

### Admin UI

- A minimal Admin panel is available in the frontend at `/admin` (requires authentication).
- From the Admin page you can:
  - Trigger model training
  - Generate predictions for a specific gameweek
  - Run a full data sync
  - View health, system stats, and Redis cache stats
  - Clear cache by pattern

## 🤝 Contributing

All contributions are welcome! Please feel free to open an issue or pull request.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
