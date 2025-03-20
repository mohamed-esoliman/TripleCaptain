#!/usr/bin/env python3
"""
TripleCaptain Setup Script
Initializes the database and sets up the development environment
"""

import asyncio
import subprocess
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))


async def run_command(command, cwd=None):
    """Run a shell command asynchronously."""
    print(f"Running: {command}")
    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd, check=True, capture_output=True, text=True
        )
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print(f"Stdout: {e.stdout}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        return False


async def check_dependencies():
    """Check if required dependencies are available."""
    print("🔍 Checking dependencies...")

    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ is required")
        return False

    print(f"✅ Python {sys.version}")

    # Check if Docker is available for databases
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        print("✅ Docker is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "⚠️  Docker not found - you'll need to set up PostgreSQL and Redis manually"
        )

    # Check if Node.js is available for frontend
    try:
        result = subprocess.run(
            ["node", "--version"], check=True, capture_output=True, text=True
        )
        print(f"✅ Node.js {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Node.js is required for the frontend")
        return False

    return True


async def setup_backend():
    """Set up the Python backend."""
    print("\n🚀 Setting up backend...")

    backend_dir = Path(__file__).parent / "backend"

    # Install Python dependencies
    print("📦 Installing Python dependencies...")
    success = await run_command(
        f"{sys.executable} -m pip install -r requirements.txt", cwd=backend_dir
    )
    if not success:
        print("❌ Failed to install Python dependencies")
        return False

    print("✅ Backend dependencies installed")
    return True


async def setup_frontend():
    """Set up the React frontend."""
    print("\n🎨 Setting up frontend...")

    frontend_dir = Path(__file__).parent / "frontend"

    # Install Node.js dependencies
    print("📦 Installing Node.js dependencies...")
    success = await run_command("npm install --legacy-peer-deps", cwd=frontend_dir)
    if not success:
        print("❌ Failed to install Node.js dependencies")
        return False

    print("✅ Frontend dependencies installed")
    return True


async def setup_database():
    """Set up the database schema."""
    print("\n💾 Setting up database...")

    # Try to start Docker services
    print("🐳 Starting Docker services...")
    success = await run_command("docker-compose up -d")
    if not success:
        print("⚠️  Could not start Docker services automatically")
        print("Please ensure PostgreSQL and Redis are running manually")
        print("PostgreSQL: localhost:5432 (user: postgres, password: password)")
        print("Redis: localhost:6379")
        input("Press Enter when your databases are ready...")
    else:
        print("✅ Docker services started")
        print("⏱️  Waiting for databases to be ready...")
        await asyncio.sleep(10)  # Wait for containers to start

    # Run database migrations
    print("🏗️  Running database migrations...")
    backend_dir = Path(__file__).parent / "backend"

    # Set environment variables
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://postgres:password@localhost:5432/triplecaptain"
    env["REDIS_URL"] = "redis://localhost:6379"

    # Try to run migration
    try:
        from app.db.database import sync_engine
        from app.db.models import Base

        print("Creating database tables...")
        Base.metadata.create_all(sync_engine)
        print("✅ Database schema created successfully")

    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        print("You may need to run migrations manually:")
        print(
            'cd backend && python -c "from app.db.database import sync_engine; from app.db.models import Base; Base.metadata.create_all(sync_engine)"'
        )
        return False

    return True


async def create_env_files():
    """Create environment configuration files."""
    print("\n⚙️  Creating environment files...")

    # Backend .env
    backend_env = Path(__file__).parent / "backend" / ".env"
    if not backend_env.exists():
        backend_env_example = Path(__file__).parent / ".env.example"
        if backend_env_example.exists():
            import shutil

            shutil.copy(backend_env_example, backend_env)
            print("✅ Created backend/.env from template")
        else:
            with open(backend_env, "w") as f:
                f.write(
                    """# Database Configuration
DATABASE_URL=postgresql://postgres:password@localhost:5432/triplecaptain
REDIS_URL=redis://localhost:6379

# Authentication
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production-please
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# FPL API
FPL_BASE_URL=https://fantasy.premierleague.com/api/

# Environment
ENVIRONMENT=development
DEBUG=true

# CORS Settings
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
"""
                )
            print("✅ Created backend/.env")

    # Frontend .env
    frontend_env = Path(__file__).parent / "frontend" / ".env"
    if not frontend_env.exists():
        frontend_env_example = Path(__file__).parent / "frontend" / ".env.example"
        if frontend_env_example.exists():
            import shutil

            shutil.copy(frontend_env_example, frontend_env)
            print("✅ Created frontend/.env from template")
        else:
            with open(frontend_env, "w") as f:
                f.write("REACT_APP_API_URL=http://localhost:8000\n")
            print("✅ Created frontend/.env")


async def initial_data_sync():
    """Perform initial data synchronization from FPL API."""
    print("\n📡 Starting initial data sync...")
    print("This will fetch team and player data from the FPL API...")

    try:
        # Import after backend is in path
        from app.services.data_pipeline import DataPipeline
        from app.ml.predictor_service import PredictorService

        pipeline = DataPipeline()
        results = await pipeline.full_data_sync()

        print(f"✅ Data sync completed:")
        print(f"   - Teams: {results['teams']}")
        print(f"   - Players: {results['players']}")
        print(f"   - Fixtures: {results['fixtures']}")

        # Attempt to train models if enough stats exist
        try:
            predictor = PredictorService()
            metrics = await predictor.train_models()
            print("✅ Model training completed:", metrics)
        except Exception as e:
            print(f"⚠️  Model training skipped/failed: {e}")

    except Exception as e:
        print(f"⚠️  Initial data sync failed: {e}")
        print("You can run this manually later with:")
        print(
            'cd backend && python -c "import asyncio; from app.services.data_pipeline import DataPipeline; asyncio.run(DataPipeline().full_data_sync())"'
        )


async def main():
    """Main setup process."""
    print("🏆 Welcome to TripleCaptain Setup!")
    print("This script will set up your FPL optimization platform")
    print("=" * 50)

    # Check dependencies
    if not await check_dependencies():
        print("\n❌ Dependency check failed. Please resolve the issues above.")
        sys.exit(1)

    # Create environment files
    await create_env_files()

    # Setup backend
    if not await setup_backend():
        print("\n❌ Backend setup failed")
        sys.exit(1)

    # Setup frontend
    if not await setup_frontend():
        print("\n❌ Frontend setup failed")
        sys.exit(1)

    # Setup database
    if not await setup_database():
        print("\n❌ Database setup failed")
        sys.exit(1)

    # Sync initial data
    await initial_data_sync()

    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("\nTo start the development environment:")
    print("1. Backend:  cd backend && uvicorn app.main:app --reload")
    print("2. Frontend: cd frontend && npm start")
    print("3. Visit:    http://localhost:3000")
    print("\nTo stop services: docker-compose down")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
