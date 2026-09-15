# Multi-Agent Fitness Coach - Local Development

A FastAPI backend for the Multi-Agent Fitness Coach application, integrating LangGraph for intelligent coaching conversations.

## Quick Start - Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ **OR** Docker
- Node.js 18+ (for frontend)
- Docker & Docker Compose (optional, for containerized development)

---

## Backend Setup

### 1. Clone Repository

```bash
cd multi-agent-coach
```

### 2. Install Python Dependencies

```bash
pip install -e .
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your local database password:

```env
DATABASE_URL=postgresql+asyncpg://postgres:adminPassw0rd@localhost:5432/systemdb
DATABASE_SCHEMA=systemdb
JWT_SECRET_KEY=your-super-secret-key-min-32-chars-long
OPENAI_API_KEY=sk-...
FRONTEND_URL=http://localhost:5174
```

### 4. Start Database

**Option A: Using Docker Compose (Recommended)**

```bash
docker-compose up -d db
```

This starts PostgreSQL on `localhost:5432` with:
- Database: `systemdb`
- User: `postgres`
- Password: `postgres`

**Option B: Using Existing PostgreSQL**

Ensure your PostgreSQL instance is running and accessible.

### 5. Run Backend

```bash
uvicorn app.main:app --reload --port 8000
```

The backend will automatically:
- ✅ Create database (if not exists)
- ✅ Create schema and tables
- ✅ Run migrations
- ✅ Create admin user (admin@example.com / ChangeMe123!)
- ✅ Start API server on http://localhost:8000

### 6. Verify Installation

**Health Check:**
```bash
curl http://localhost:8000/health
```

**API Documentation:**
Open http://localhost:8000/docs in your browser.

### 7. Test Endpoints

**Register User:**
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "name": "Test User"
  }'
```

**Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "ChangeMe123!"
  }'
```

Save the `access_token` for subsequent requests.

**Test Chat:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "messages": [{"role": "user", "content": "What workout should I do?"}],
    "session_id": "chat_abc123def456789"
  }'
```

---

## Frontend Setup

### 1. Navigate to Frontend

```bash
cd frontend
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Configure Environment

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

### 4. Start Development Server

```bash
npm run dev
```

Frontend will be available at: http://localhost:5174

### 5. Integration Details

For detailed frontend integration instructions, see:
- **[docs/PHASE-5-FRONTEND.md](docs/PHASE-5-FRONTEND.md)** - Complete integration guide
- **[frontend/SETUP.md](frontend/SETUP.md)** - Frontend setup details

---

## All-in-One Local Development

### Using Docker Compose

Start everything with one command:

```bash
docker-compose up -d
```

This starts:
- ✅ Backend API (port 8000)
- ✅ Recovery Agent (port 8001, private microservice)
- ✅ PostgreSQL database (port 5432)
- ✅ Redis (port 6379, optional for session testing)

**View logs:**
```bash
docker-compose logs -f api
```

**Stop all services:**
```bash
docker-compose down
```

---

## Development Workflow (Additional Info)

### Hot Reload

Backend automatically reloads on code changes:

```bash
uvicorn app.main:app --reload --port 8000
```

### Code Formatting

```bash
# Format code
ruff format app/

# Check for issues
ruff check app/
```

### Database Migrations

Migrations run automatically on startup. To manually run:

```bash
python -m app.db.seed
```

### Testing

```bash
# Run tests (when available)
pytest tests/ -v --cov=app
```

---

## Local Troubleshooting

### Database Connection Failed

```bash
# Check PostgreSQL is running
docker-compose ps db

# Verify connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL
```

### Port 8000 Already in Use

```bash
# Windows: Find process
netstat -ano | findstr :8000
# Kill process
taskkill /PID <PID> /F

# Use different port
uvicorn app.main:app --reload --port 8001
```

### Admin User Not Created

Check backend logs for:
```
"Admin user seeding completed"
```

If missing, restart backend or manually seed:
```bash
python -c "from app.db.seed import seed_admin_user; from app.db.database import AsyncSessionLocal; import asyncio; asyncio.run(seed_admin_user(AsyncSessionLocal()))"
```

### JWT Validation Failed

- Ensure `JWT_SECRET_KEY` is set in `.env` (min 32 characters)
- Check token format: `Authorization: Bearer <token>`
- Default token expiry: 24 hours

---

## Default Credentials

**Admin User** (auto-created on first startup):
- Email: `admin@example.com`
- Password: `ChangeMe123!`

**Customize in `.env`:**
```env
SEED_ADMIN_EMAIL=your-admin@example.com
SEED_ADMIN_PASSWORD=YourSecurePassword123!
SEED_ADMIN_NAME=Your Admin Name
```

---

## Project Structure

```
multi-agent-coach/
├── app/                        # FastAPI backend
│   ├── api/
│   │   ├── routes/            # API endpoints
│   │   └── schemas/           # Pydantic models
│   ├── services/              # Business logic
│   ├── db/                    # Database layer
│   ├── utils/                 # Utilities
│   ├── config.py              # Configuration
│   └── main.py                # Application entry
├── agents/                     # LangGraph agents
├── tools/                      # Agent tools
├── frontend/                   # React frontend
├── docker-compose.yml          # Local dev services
├── Dockerfile                  # Production container
└── .env.example                # Environment template
```

---

## API Quick Reference

### Recovery Data Table

Sign in with a real administrator account and open **Recovery Table** (`/recovery-table`) to manage
**Sleep logs**, **Recovery check-ins**, and **Recovery assessments**. Each tab
supports paginated listing, filtering by user ID, creating, editing, and deleting
records. Expand an assessment row to inspect its response and tool trace.

The frontend uses `VITE_API_BASE_URL` and the signed-in user's bearer token to
call the backend. The backend connects using `DATABASE_URL` from `.env` to the
existing `systemdb` recovery tables created by migration `003`. Database
credentials and the Recovery Agent's internal token stay on the server.
Restart the backend after updating to register the new routes; the Recovery
Agent service does not need to be running to manage these records.

Records require an existing user ID. Sleep duration is in minutes (0–1440),
sleep quality is 1–5, and energy, soreness, and stress are 1–10. Assessment
responses use a JSON object and tool traces use a JSON array of strings.
Editing an assessment changes the stored record; it does not run a new assessment.

All recovery CRUD endpoints require an enabled administrator account:

- `GET /api/recovery/{resource}?page=1&page_size=10&user_id=1` — list records
- `POST /api/recovery/{resource}` — create a record
- `PUT /api/recovery/{resource}/{id}` — update a record
- `DELETE /api/recovery/{resource}/{id}` — delete a record

`{resource}` is `sleep-logs`, `check-ins`, or `assessments`. The list response
contains `items` and `total`. Creation returns 201, deletion returns 204,
invalid fields return 422, and missing records return 404.

Run API contract tests with `python -m pytest tests/test_recovery_crud.py -q`.

### Authentication
- `POST /api/auth/login` - Login
- `POST /api/auth/register` - Register
- `POST /api/auth/refresh` - Refresh token

### Chat
- `POST /api/chat` - Send message
- `GET /api/chat/stream` - Stream response (SSE)
- `POST /api/chat/summary` - Get summary
- `DELETE /api/chat/history/{id}` - Clear history

### Session
- `POST /api/session` - Create session
- `GET /api/session/{id}` - Get details
- `DELETE /api/session/{id}` - Delete session

---

## Next Steps

### For Development
1. ✅ Backend running locally
2. ✅ Frontend running locally
3. ✅ Database setup complete
4. → Start building features!

### For Production Deployment
See **[README-to-be.md](README-to-be.md)** for:
- AWS deployment guide
- PostgreSQL container deployment
- Production configuration
- Scaling and monitoring

---

## Documentation

**Local Development:**
- **[README.md](README.md)** - This file (local setup)
- **[frontend/SETUP.md](frontend/SETUP.md)** - Frontend setup

**Technical:**
- **[docs/API-REFERENCE.md](docs/API-REFERENCE.md)** - Complete API docs
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Troubleshooting guide

**Deployment:**
- **[README-to-be.md](README-to-be.md)** - AWS deployment guide
- **[docs/PHASE-6-AWS.md](docs/PHASE-6-AWS.md)** - Detailed AWS guide
- **[docs/DEPLOYMENT-CHECKLIST.md](docs/DEPLOYMENT-CHECKLIST.md)** - Production checklist

---
