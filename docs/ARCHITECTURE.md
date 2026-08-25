# System Architecture

**Version**: 1.0.0  
**Last Updated**: 2026-08-24

---

## Overview

Multi-Agent Coach is a fitness coaching application powered by multiple AI agents orchestrated through LangGraph, exposed via a FastAPI backend, and accessed through a React frontend.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                            │
│  ┌─────────────────┐         ┌─────────────────┐            │
│  │  React App      │         │  Mobile App     │            │
│  │  (TypeScript)   │         │  (Future)       │            │
│  │  Port: 5174     │         │                 │            │
│  └────────┬────────┘         └─────────────────┘            │
│           │                                                  │
│           │ HTTP/HTTPS + JWT                                 │
└───────────┼──────────────────────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           Application Load Balancer (ALB)              │  │
│  │           - HTTPS Termination                          │  │
│  │           - Rate Limiting                              │  │
│  │           - Health Checks                              │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────┬──────────────────────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────────────────────┐
│                   APPLICATION LAYER                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           FastAPI Backend (ECS Fargate)                │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  Authentication Layer                            │  │  │
│  │  │  - JWT Validation                                │  │  │
│  │  │  - Role-Based Access Control                     │  │  │
│  │  │  - get_current_user dependency                   │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  API Routes                                      │  │  │
│  │  │  - /api/auth/* (login, register, refresh)        │  │  │
│  │  │  - /api/chat/* (POST, GET /stream, summary)      │  │  │
│  │  │  - /api/session/* (CRUD operations)              │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  Business Logic (Services)                       │  │  │
│  │  │  - JWT Service                                   │  │  │
│  │  │  - Session Manager (In-memory / Redis)           │  │  │
│  │  │  - User Profile Service                          │  │  │
│  │  │  - Agent Orchestrator                            │  │  │
│  │  │  - S3 Archival Service                           │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  Multi-Agent System (LangGraph)                  │  │  │
│  │  │  - Head Coach (Orchestrator)                     │  │  │
│  │  │  - Training Agent                                │  │  │
│  │  │  - Nutrition Agent                               │  │  │
│  │  │  - Recovery Agent                                │  │  │
│  │  │  - Summarizer Agent                              │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────┬──────────────────────────────────────────────────┘
            │
            ├──────────────────┬──────────────────┬─────────────┐
            │                  │                  │             │
┌───────────▼──────┐  ┌────────▼──────┐  ┌──────▼────────┐ ┌──▼──────────┐
│   DATA LAYER     │  │  CACHE LAYER  │  │ STORAGE LAYER │ │ MONITORING  │
│  ┌────────────┐  │  │ ┌──────────┐  │  │ ┌──────────┐  │ │ ┌────────┐  │
│  │ PostgreSQL │  │  │ │ Elasti   │  │  │ │   S3     │  │ │ │Cloud   │  │
│  │    (RDS)   │  │  │ │ Cache    │  │  │ │  Bucket  │  │ │ │Watch   │  │
│  │            │  │  │ │ (Redis)  │  │  │ │          │  │ │ │        │  │
│  │ - Users    │  │  │ │          │  │  │ │ - Chat   │  │ │ │ - Logs │  │
│  │ - Profiles │  │  │ │ -Sessions│  │  │ │ History  │  │ │ │ -Metrics│ │
│  │ - Fitness  │  │  │ │          │  │  │ │          │  │ │ │ -Alarms│  │
│  └────────────┘  │  │ └──────────┘  │  │ └──────────┘  │ │ └────────┘  │
└──────────────────┘  └───────────────┘  └───────────────┘ └─────────────┘
```

---

## Component Details

### 1. Frontend (React + TypeScript)

**Location**: `frontend/`  
**Port**: 5174 (development)  
**Framework**: React 18 + TypeScript + Vite

**Key Components**:
- **Authentication**: `src/lib/auth.ts` - Login, register, token management
- **Chat API**: `src/lib/chatbot-api.ts` - Chat endpoints, SSE streaming
- **State Management**: Zustand for auth state
- **UI Components**: DeepChatBox for chat interface

**Data Flow**:
```
User Action → Auth Store → API Call → Backend → Response → UI Update
```

---

### 2. Backend (FastAPI + Python)

**Location**: `app/`  
**Port**: 8000  
**Framework**: FastAPI + Uvicorn

#### 2.1 API Routes (`app/api/routes/`)

**Authentication** (`auth.py`):
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `POST /api/auth/refresh` - Token refresh

**Chat** (`chat.py`):
- `POST /api/chat` - Send message, get response
- `GET /api/chat/stream` - Stream response (SSE)
- `POST /api/chat/summary` - Request summary
- `DELETE /api/chat/history/{id}` - Clear history

**Session** (`session.py`):
- `POST /api/session` - Create session
- `GET /api/session/{id}` - Get details
- `DELETE /api/session/{id}` - Delete session
- `POST /api/session/clear` - Clear messages

#### 2.2 Services (`app/services/`)

**JWT Service** (`jwt_service.py`):
- Create JWT tokens with user claims
- Validate and decode tokens
- Handle token refresh

**Session Manager** (`session_manager.py`):
- In-memory session storage (dev)
- Redis integration (production)
- Background cleanup task
- S3 archival

**User Profile Service** (`user_profile_service.py`):
- CRUD operations for user profiles
- Fitness profile management
- Cache invalidation

**Agent Orchestrator** (`agent_orchestrator.py`):
- LangGraph integration
- Multi-agent coordination
- Response aggregation

#### 2.3 Database Layer (`app/db/`)

**Models** (`models.py`):
```python
User:
  - id (BIGINT, PK)
  - email (VARCHAR, UNIQUE)
  - password_hash (VARCHAR)
  - name (VARCHAR)
  - role (VARCHAR: ADMIN/STAFF/USER)
  - enabled (BOOLEAN)
  - created_at (TIMESTAMP)

UserFitnessProfile:
  - user_id (BIGINT, PK, FK)
  - fitness_goal (VARCHAR)
  - fitness_level (VARCHAR)
  - weight_kg (NUMERIC)
  - height_cm (NUMERIC)
  - age (INTEGER)
  - updated_at (TIMESTAMP)
```

**Migrations** (`migrations/`):
- `000_create_users_table.sql` - Initial schema
- `001_create_tables.sql` - Additional tables
- `002_seed_data.sql` - Seed data

**Setup** (`setup.py`):
- Auto-create database
- Auto-create schema
- Auto-run migrations
- Auto-seed admin user

---

### 3. Multi-Agent System (LangGraph)

**Location**: `agents/`, `tools/`  
**Orchestration**: LangGraph state graph

#### Agent Roles:

**Head Coach** (Orchestrator):
- Routes queries to specialists
- Aggregates responses
- Maintains conversation context

**Training Agent**:
- Workout planning
- Exercise recommendations
- Progress tracking

**Nutrition Agent**:
- Meal planning
- Macro calculations
- Dietary advice

**Recovery Agent**:
- Rest recommendations
- Injury prevention
- Sleep optimization

**Summarizer Agent**:
- Session summaries
- Key takeaways
- Action items

#### Data Flow:
```
User Query → Head Coach → Route to Specialists
                ↓
         Training    Nutrition    Recovery
            ↓           ↓            ↓
         Aggregate Responses
                ↓
         Format & Return
```

---

### 4. Database (PostgreSQL)

**Location**: RDS (production) / Docker (dev)  
**Schema**: `systemdb`  
**Port**: 5432

#### Tables:

**users**:
```sql
CREATE TABLE systemdb.users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'USER',
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**user_fitness_profiles**:
```sql
CREATE TABLE systemdb.user_fitness_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES systemdb.users(id),
    fitness_goal VARCHAR(255) DEFAULT 'general fitness',
    fitness_level VARCHAR(50) DEFAULT 'beginner',
    weight_kg NUMERIC(5,2),
    height_cm NUMERIC(5,2),
    age INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Indexes:
- `idx_users_email` - Fast email lookups
- `idx_user_fitness_profiles_user_id` - FK index

---

### 5. Session Storage

**Development**: In-memory dict  
**Production**: Redis (ElastiCache)

#### Session Structure:
```python
{
    "session_id": "chat_abc123def456789",
    "user_id": 123,
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "created_at": "2026-08-24T12:00:00Z",
    "last_activity": "2026-08-24T12:05:00Z"
}
```

#### Lifecycle:
1. **Create**: Frontend generates session ID, backend validates
2. **Active**: Messages stored in memory/Redis
3. **Archival**: After each message, async save to S3
4. **Expiry**: 24 hours of inactivity (configurable)
5. **Cleanup**: Background task removes expired sessions

---

### 6. Storage (S3)

**Purpose**: Chat history archival  
**Bucket**: `multi-agent-coach-chat-history`  
**Prefix**: `chat-history/{user_id}/{session_id}.json`

#### Object Structure:
```json
{
    "session_id": "chat_abc123def456789",
    "user_id": 123,
    "messages": [...],
    "created_at": "2026-08-24T12:00:00Z",
    "archived_at": "2026-08-24T12:05:00Z"
}
```

#### Features:
- Server-side encryption (SSE-S3)
- Versioning enabled
- Lifecycle policies (transition to Glacier)
- Public access blocked

---

## Authentication Flow

```
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│  User   │      │Frontend │      │ Backend │      │   DB    │
└────┬────┘      └────┬────┘      └────┬────┘      └────┬────┘
     │                │                │                │
     │ 1. Login       │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ 2. Validate    │                │
     │                │ credentials    │                │
     │                │───────────────>│                │
     │                │                │                │
     │                │                │ 3. Query user  │
     │                │                │───────────────>│
     │                │                │                │
     │                │                │ 4. User data   │
     │                │                │<───────────────│
     │                │                │                │
     │                │ 5. Create JWT  │                │
     │                │<───────────────│                │
     │                │                │                │
     │ 6. Token       │                │                │
     │<───────────────│                │                │
     │                │                │                │
     │ 7. Store token │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │ 8. API Request │                │                │
     │ + JWT          │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ 9. Forward JWT │                │
     │                │───────────────>│                │
     │                │                │                │
     │                │                │ 10. Validate    │
     │                │                │     JWT         │
     │                │                │                │
     │                │                │ 11. Process     │
     │                │                │     request     │
     │                │                │                │
     │ 12. Response   │                │                │
     │<───────────────│                │                │
     └                └                └                └
```

---

## Chat Message Flow

```
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│  User   │      │Frontend │      │ Backend │      │ Agents  │
└────┬────┘      └────┬────┘      └────┬────┘      └────┬────┘
     │                │                │                │
     │ 1. Type msg    │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ 2. Add to UI   │                │
     │                │───────────────>│                │
     │                │                │                │
     │                │ 3. POST /chat  │                │
     │                │ + JWT + sess   │                │
     │                │───────────────>│                │
     │                │                │                │
     │                │                │ 4. Validate JWT │
     │                │                │───────────────>│
     │                │                │                │
     │                │                │ 5. Get session  │
     │                │                │───────────────>│
     │                │                │                │
     │                │                │ 6. Route to     │
     │                │                │ Head Coach      │
     │                │                │───────────────>│
     │                │                │                │
     │                │                │                │ 7. Distribute
     │                │                │                │ to specialists
     │                │                │                │────────┐
     │                │                │                │        │
     │                │                │                │ 8. Responses
     │                │                │                │<───────┘
     │                │                │                │
     │                │                │ 9. Aggregate    │
     │                │                │<────────────────│
     │                │                │                │
     │                │                │ 10. Save to     │
     │                │                │ session + S3    │
     │                │                │                │
     │                │ 11. Stream     │                │
     │                │ response (SSE) │                │
     │                │<───────────────│                │
     │                │                │                │
     │ 12. Display    │                │                │
     │<───────────────│                │                │
     └                └                └                └
```

---

## Deployment Architecture (AWS)

```
┌─────────────────────────────────────────────────────────────┐
│                         VPC                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Public Subnets                           │  │
│  │  ┌─────────────┐                                      │  │
│  │  │  ALB        │                                      │  │
│  │  │  (Internet) │                                      │  │
│  │  └──────┬──────┘                                      │  │
│  └─────────┼──────────────────────────────────────────────┘  │
│            │                                                  │
│  ┌─────────▼──────────────────────────────────────────────┐  │
│  │              Private Subnets                           │  │
│  │                                                        │  │
│  │  ┌─────────────────┐  ┌─────────────────┐             │  │
│  │  │  ECS Task 1     │  │  ECS Task 2     │             │  │
│  │  │  (Fargate)      │  │  (Fargate)      │             │  │
│  │  │  FastAPI        │  │  FastAPI        │             │  │
│  │  └────────┬────────┘  └────────┬────────┘             │  │
│  │           │                    │                       │  │
│  │  ┌────────▼────────────────────▼────────┐             │  │
│  │  │         NAT Gateway                  │             │  │
│  │  └──────────────────────────────────────┘             │  │
│  │                                                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │   RDS        │  │  ElastiCache │  │  S3 Bucket   │ │  │
│  │  │  PostgreSQL  │  │    Redis     │  │  (Chat Hist) │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Security Architecture

### Authentication
- JWT-based stateless authentication
- Bcrypt password hashing (cost factor: 12)
- Token expiry: 24 hours (configurable)
- Refresh token rotation

### Authorization
- Role-based access control (ADMIN/STAFF/USER)
- Session ownership validation
- Protected API endpoints

### Data Security
- HTTPS/TLS for all communications
- RDS encryption at rest
- S3 server-side encryption
- Secrets stored in AWS Secrets Manager

### Network Security
- VPC isolation
- Security groups with minimal access
- Private subnets for databases
- ALB with HTTPS termination

---

## Scalability Considerations

### Horizontal Scaling
- **ECS Auto-scaling**: Based on CPU/memory utilization
- **RDS Read Replicas**: For read-heavy workloads
- **Redis Cluster**: For session distribution

### Vertical Scaling
- **ECS Tasks**: Increase CPU/memory allocation
- **RDS**: Upgrade instance class
- **Redis**: Upgrade node type

### Caching Strategy
- **Redis**: Session storage, user profiles
- **Application**: LRU cache for frequent queries
- **CDN**: Static assets, frontend bundle

### Database Optimization
- **Indexes**: Email, foreign keys
- **Connection Pooling**: PgBouncer for high concurrency
- **Partitioning**: By user_id for large tables

---

## Monitoring & Observability

### Metrics (CloudWatch)
- API latency (p50, p95, p99)
- Error rates (4xx, 5xx)
- Database connections
- Cache hit/miss ratio
- Agent response times

### Logging (CloudWatch Logs)
- Application logs (structured JSON)
- Access logs (ALB)
- Database logs (RDS)
- Audit logs (user actions)

### Alarms (CloudWatch)
- High CPU utilization (>80%)
- High memory utilization (>80%)
- Database connections (>100)
- Error rate (>5%)
- Latency (>1s p95)

### Tracing (X-Ray)
- Request tracing across services
- Performance bottlenecks
- Dependency mapping

---

## Disaster Recovery

### Backup Strategy
- **RDS**: Automated daily backups, 7-day retention
- **S3**: Versioning enabled, cross-region replication
- **Redis**: Daily snapshots

### Recovery Time Objective (RTO)
- **Target**: < 1 hour
- **Strategy**: Multi-AZ deployment, automated failover

### Recovery Point Objective (RPO)
- **Target**: < 15 minutes
- **Strategy**: Continuous S3 archival, RDS point-in-time recovery

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Frontend | React + TypeScript | 18.x |
| Frontend Build | Vite | 5.x |
| Backend | FastAPI | 0.115.x |
| Backend Runtime | Python | 3.12 |
| Database | PostgreSQL | 16.x |
| Cache | Redis | 7.x |
| Multi-Agent | LangGraph | 0.6.x |
| LLM | OpenAI GPT | gpt-5-nano |
| Container | Docker | Latest |
| Orchestration | AWS ECS Fargate | - |
| Load Balancer | AWS ALB | - |
| Storage | AWS S3 | - |
| Monitoring | AWS CloudWatch | - |

---

**End of Architecture Document**
