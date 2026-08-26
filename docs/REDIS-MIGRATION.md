# Redis Migration Guide

**Purpose**: Migrate from in-memory session storage to Redis for production deployment  
**When**: Ready for AWS deployment or multi-instance setup  
**Difficulty**: Medium  
**Estimated Time**: 2-3 hours

---

## Overview

The current implementation uses in-memory session storage (Python dict) which:
- ✅ Fast and simple for development
- ✅ No external dependencies
- ❌ Lost on application restart
- ❌ Not shared across multiple instances
- ❌ No TTL-based expiration

Redis provides:
- ✅ Persistent storage (with AOF/RDB)
- ✅ Shared across instances
- ✅ Automatic TTL-based expiration
- ✅ High performance
- ✅ AWS ElastiCache support

---

## Prerequisites

### 1. Install Redis Client

```bash
pip install redis asyncio
# or
pip install redis[hiredis]
```

### 2. Setup Redis Server

**Local Development:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**AWS Production:**
- Create ElastiCache for Redis cluster
- Configure security groups
- Get Redis endpoint URL

---

## Implementation Steps

### Step 1: Update Dependencies

**File**: `pyproject.toml`

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "redis>=5.0.0",
    "asyncio-redis>=0.16.0",
]
```

### Step 2: Create Redis Session Store

**File**: `app/services/session_store.py`

```python
"""
Redis session store for production use.

Implements the same interface as in-memory SessionManager
but uses Redis for storage.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import redis.asyncio as redis

from app.config import get_settings
from app.services.session_manager import Session

logger = logging.getLogger(__name__)
settings = get_settings()


class RedisSessionStore:
    """Redis-based session storage."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.client: Optional[redis.Redis] = None
        self.default_ttl = settings.SESSION_EXPIRY_HOURS * 3600  # Convert to seconds

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if not self.redis_url:
            logger.warning("Redis URL not configured, using in-memory fallback")
            return

        try:
            self.client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            raise

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis")

    def _get_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"session:{session_id}"

    async def create_session(
        self,
        user_id: int,
        profile: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> Session:
        """Create new session in Redis."""
        if not self.client:
            raise RuntimeError("Redis not connected")

        import uuid
        if not session_id:
            session_id = f"chat_{uuid.uuid4().hex[:16]}"

        session = Session(session_id=session_id, user_id=user_id, profile=profile)

        # Store in Redis with TTL
        key = self._get_key(session_id)
        await self.client.setex(
            key,
            self.default_ttl,
            json.dumps(session.to_dict()),
        )

        logger.info("Created session in Redis: %s", session_id)
        return session

    async def get_session(self, session_id: str, user_id: int) -> Optional[Session]:
        """Get session from Redis."""
        if not self.client:
            return None

        key = self._get_key(session_id)
        data = await self.client.get(key)

        if not data:
            return None  # Session expired or not found

        session = Session.from_dict(json.loads(data))

        # Authorization check
        if session.user_id != user_id:
            raise PermissionError("Cannot access another user's session")

        # Refresh TTL on access
        await self.client.expire(key, self.default_ttl)

        return session

    async def update_session(
        self,
        session_id: str,
        user_id: int,
        messages: list,
        agent_state: Optional[Dict] = None,
    ) -> bool:
        """Update session in Redis."""
        if not self.client:
            return False

        session = await self.get_session(session_id, user_id)
        if not session:
            return False

        # Update session data
        session.messages.extend(messages)
        session.last_activity = datetime.utcnow()
        if agent_state:
            session.agent_state = agent_state

        # Save back to Redis
        key = self._get_key(session_id)
        await self.client.setex(
            key,
            self.default_ttl,
            json.dumps(session.to_dict()),
        )

        return True

    async def clear_session(self, session_id: str, user_id: int) -> bool:
        """Clear session messages."""
        if not self.client:
            return False

        session = await self.get_session(session_id, user_id)
        if not session:
            return False

        # Clear messages but keep session
        session.messages = []
        session.agent_state = {}
        session.last_activity = datetime.utcnow()

        # Save back to Redis
        key = self._get_key(session_id)
        await self.client.setex(
            key,
            self.default_ttl,
            json.dumps(session.to_dict()),
        )

        return True

    async def delete_session(self, session_id: str, user_id: int) -> bool:
        """Delete session from Redis."""
        if not self.client:
            return False

        session = await self.get_session(session_id, user_id)
        if not session:
            return False

        key = self._get_key(session_id)
        await self.client.delete(key)

        logger.info("Deleted session from Redis: %s", session_id)
        return True

    async def cleanup_expired_sessions(self) -> int:
        """
        Cleanup expired sessions.

        Note: Redis automatically expires keys with TTL,
        so this method is mostly for monitoring.
        """
        # Redis handles TTL expiration automatically
        # This method is for manual cleanup if needed
        return 0
```

### Step 3: Update Session Manager

**File**: `app/services/session_manager.py`

Modify to support both in-memory and Redis:

```python
# Add at the top
from typing import Union
from app.services.session_store import RedisSessionStore

# Modify SessionManager class
class SessionManager:
    def __init__(self, use_redis: bool = False):
        self.use_redis = use_redis
        self.sessions: Dict[str, Session] = {}  # In-memory
        self.redis_store: Optional[RedisSessionStore] = None  # Redis
        
        if use_redis:
            self.redis_store = RedisSessionStore()
            
    async def initialize(self) -> None:
        """Initialize session manager."""
        if self.use_redis and self.redis_store:
            await self.redis_store.connect()
    
    async def shutdown(self) -> None:
        """Shutdown session manager."""
        if self.use_redis and self.redis_store:
            await self.redis_store.disconnect()
    
    # Update methods to use Redis if configured
    async def create_session(self, user_id: int, profile: Dict, session_id: Optional[str] = None) -> Session:
        if self.use_redis and self.redis_store:
            return await self.redis_store.create_session(user_id, profile, session_id)
        else:
            # Existing in-memory implementation
            ...
    
    async def get_session(self, session_id: str, user_id: int) -> Optional[Session]:
        if self.use_redis and self.redis_store:
            return await self.redis_store.get_session(session_id, user_id)
        else:
            # Existing in-memory implementation
            ...
    
    # Update other methods similarly...
```

### Step 4: Update Configuration

**File**: `app/config.py`

```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # Redis Configuration
    REDIS_URL: Optional[str] = None
    
    @property
    def is_redis_configured(self) -> bool:
        return bool(self.REDIS_URL)
```

### Step 5: Update Main Application

**File**: `app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    
    # Initialize session manager
    session_mgr = get_session_manager()
    if settings.is_redis_configured:
        await session_mgr.initialize()
        logger.info("Session manager initialized with Redis")
    
    yield
    
    # Shutdown
    if settings.is_redis_configured:
        await session_mgr.shutdown()
    
    await close_db()
```

### Step 6: Update Environment Variables

**File**: `.env` or `.env.example`

```env
# Redis Configuration (Production Only)
REDIS_URL=redis://localhost:6379/0

# AWS ElastiCache Example
# REDIS_URL=redis://your-cluster.xxx.cache.amazonaws.com:6379/0
```

**File**: `docker-compose.yml`

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

---

## Testing

### 1. Local Testing

```bash
# Start Redis
docker-compose up -d redis

# Set environment variable
export REDIS_URL=redis://localhost:6379/0

# Run backend
uvicorn app.main:app --reload

# Test session creation
curl -X POST http://localhost:8000/api/session \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. Verify Redis Storage

```bash
# Connect to Redis
redis-cli

# List all session keys
KEYS session:*

# Get session data
GET session:chat_abc123def456789

# Check TTL
TTL session:chat_abc123def456789
```

### 3. Test Expiration

```python
# Python script to test TTL
import redis
r = redis.Redis()

# Check session TTL
ttl = r.ttl('session:chat_abc123def456789')
print(f"Session expires in: {ttl} seconds")
```

---

## AWS ElastiCache Setup

### 1. Create ElastiCache Cluster

**AWS Console**:
1. Go to ElastiCache
2. Create cluster (Redis)
3. Choose node type (cache.t3.micro for dev)
4. Configure security groups
5. Get endpoint URL

### 2. Configure Security Groups

**Inbound Rules**:
- Type: Redis
- Port: 6379
- Source: ECS security group

### 3. Update Environment

**AWS Secrets Manager** or **ECS Task Definition**:

```json
{
  "REDIS_URL": "redis://your-cluster.xxx.cache.amazonaws.com:6379/0"
}
```

---

## Migration Checklist

- [ ] Install redis package
- [ ] Create RedisSessionStore class
- [ ] Update SessionManager to support Redis
- [ ] Add REDIS_URL to config
- [ ] Update docker-compose.yml
- [ ] Test locally with Redis
- [ ] Verify session persistence
- [ ] Test session expiration
- [ ] Deploy to AWS
- [ ] Create ElastiCache cluster
- [ ] Update ECS environment variables
- [ ] Monitor Redis metrics

---

## Rollback Plan

If Redis causes issues, rollback to in-memory:

1. Set `REDIS_URL` to empty in environment
2. Restart application
3. Sessions will use in-memory storage

---

## Performance Considerations

### In-Memory
- **Latency**: < 1ms
- **Throughput**: 100k+ ops/sec
- **Limitation**: Single instance only

### Redis
- **Latency**: 1-5ms (local), 5-20ms (network)
- **Throughput**: 50k+ ops/sec
- **Benefit**: Multi-instance support

---

## Monitoring

### Redis Metrics to Watch

- **Memory Usage**: `used_memory`
- **Connections**: `connected_clients`
- **Hit Rate**: `keyspace_hits / (keyspace_hits + keyspace_misses)`
- **Evictions**: `evicted_keys`

### CloudWatch (AWS)

- CPU utilization
- Freeable memory
- Network throughput
- Cache hits/misses

---

## Troubleshooting

### Connection Failed

```
Error: Connection refused
```

**Solution**:
- Check Redis is running: `docker-compose ps redis`
- Verify REDIS_URL format
- Check firewall/security groups

### Session Not Persisting

```
Session lost after restart
```

**Solution**:
- Verify Redis AOF/RDB persistence enabled
- Check Redis memory limit
- Verify TTL not too short

### High Latency

```
Session operations slow
```

**Solution**:
- Check network latency
- Use Redis pipelining
- Consider connection pooling

---

## Next Steps

After Redis migration:

1. **Add Monitoring**: Redis metrics dashboard
2. **Add Caching**: Cache user profiles, agent responses
3. **Add Pub/Sub**: Real-time notifications
4. **Add Clustering**: Redis Cluster for high availability

---

**Last Updated**: 2026-08-24  
**Version**: 1.0.0
