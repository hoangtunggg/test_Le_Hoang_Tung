# Fabbi Todo App — Developer Assessment Codebase

A full-stack Todo application built with JWT authentication, designed for developer skill evaluation.

## Tech Stack

### Backend

- **FastAPI** — Python async web framework
- **PostgreSQL** — Relational database
- **Redis** — Caching layer
- **SQLAlchemy 2.0** — Async ORM
- **Alembic** — Database migrations
- **Pydantic v2** — Data validation

### Frontend

- **React 19** + **TypeScript** — UI framework
- **Vite** — Build tool
- **Tailwind CSS v4** — Utility-first CSS
- **shadcn/ui** — Component library
- **TanStack React Query** — Server state management
- **react-hook-form** + **Zod** — Form handling & validation
- **React Router** — Client-side routing

### Infrastructure

- **Docker Compose** — Container orchestration
- **Dockerized** backend + frontend + PostgreSQL + Redis

## Getting Started

### Prerequisites

- Docker & Docker Compose installed
- Git

### Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd fabbi

# Copy environment variables
cp .env.example .env

# Replace every replace_with_* placeholder. Generate independent secrets with:
openssl rand -hex 32

# Start all services
docker-compose up --build

# Seed the database with a demo user and sample TODOs
docker compose exec backend python -m app.db.seed
```

The application will be available at:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Demo Login credentials**:
  - Email: `demo@test.com`
  - Password: `Demo@123`

PostgreSQL and Redis are exposed to the host on loopback only. Redis requires
the password configured in `.env`. Compose injects operational secrets at
container runtime; they are not baked into either application image.

The former operational environment files were tracked historically. Removing
them from the current tree does not erase earlier Git revisions, so rotate any
credential that was used outside local development.

PostgreSQL applies its initialization variables only when creating a new data
directory. For an existing `postgres_data` volume, update the database role and
database to match `.env`; alternatively, recreate the volume only when its local
data is disposable.

By default the seed command creates 100 users and 1,000 TODOs so the assessment is quick to set up. To test performance with a larger dataset, pass seed variables explicitly:

```bash
docker compose exec -e SEED_USERS=10000 -e SEED_TODOS=1000000 backend python -m app.db.seed
```

### Local Development (without Docker)

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate.bat
pip install -r requirements.txt
cp .env.example .env

# Replace the placeholders with the credentials used by local PostgreSQL/Redis.

# Start PostgreSQL and Redis locally, then run migrations and seed data:
alembic upgrade head
python -m app.db.seed

# Start backend server
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## API Endpoints

### Authentication

| Method | Endpoint                | Description           |
| ------ | ----------------------- | --------------------- |
| POST   | `/api/v1/auth/register` | Register a new user   |
| POST   | `/api/v1/auth/login`    | Login and get tokens  |
| POST   | `/api/v1/auth/refresh`  | Refresh access token  |
| POST   | `/api/v1/auth/logout`   | Logout user           |
| GET    | `/api/v1/auth/me`       | Get current user info |

### Todos

| Method | Endpoint             | Description            |
| ------ | -------------------- | ---------------------- |
| GET    | `/api/v1/todos`      | List todos (paginated) |
| POST   | `/api/v1/todos`      | Create a new todo      |
| GET    | `/api/v1/todos/{id}` | Get a specific todo    |
| PUT    | `/api/v1/todos/{id}` | Update a todo          |
| DELETE | `/api/v1/todos/{id}` | Delete a todo          |

## Project Structure

```
fabbi/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API route handlers
│   │   ├── core/            # Config, security, Redis
│   │   ├── db/              # Database setup
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic validation
│   │   ├── services/        # Business logic
│   │   └── main.py          # FastAPI app
│   ├── alembic/             # DB migrations
│   └── tests/               # Test suite
├── frontend/
│   └── src/
│       ├── components/ui/   # shadcn/ui components
│       ├── features/        # Feature modules (auth, todos)
│       ├── lib/             # Utilities (API, query client)
│       ├── pages/           # Route pages
│       └── router/          # React Router config
└── docker-compose.yml
```

## Running Tests

### Backend Automated Tests
```bash
cd backend
pytest tests/ -v
```

### Frontend E2E Tests (Playwright)
With the Docker services running, run the Playwright suite from the frontend directory:
```bash
# Headless (default)
cd frontend
npx playwright test

# Headed
npx playwright test --headed
```

### Database Performance Benchmarking
To test database indexing and query execution times with 1 million records:
```bash
docker compose exec -e SEED_USERS=10000 -e SEED_TODOS=1000000 backend python -m app.db.seed
```
Connect to PostgreSQL container to run `EXPLAIN ANALYZE`:
```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```
