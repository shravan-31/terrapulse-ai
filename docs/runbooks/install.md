# SatQuery AI — Installation & System Runbook

## 1. Prerequisites
- **Python:** 3.10+ (Tested on Python 3.13)
- **Node.js:** 18+ & npm
- **Database:** PostgreSQL 15+ (with PostGIS optional / gracefully handled)
- **Cache/Broker:** Redis 6+ (for Celery background worker)

## 2. Backend Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   # Linux/macOS
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Environment Configuration:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials:
   # DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/satquery
   # REDIS_URL=redis://localhost:6379/0
   # OPERATOR_USERNAME=operator
   # OPERATOR_PASSWORD=your_secure_password
   ```

4. Database Migrations:
   ```bash
   python scripts/migrate.py
   ```

5. Start the FastAPI API Server:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir backend
   ```

6. Start Celery Worker (in a separate terminal):
   ```bash
   python -m celery -A app.workers.celery_app worker --loglevel=info
   ```

## 3. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   ```

2. Start the Vite development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.
