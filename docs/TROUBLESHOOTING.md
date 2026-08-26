# Troubleshooting Guide

**Last Updated**: 2026-08-24  
**Version**: 1.0.0

---

## Quick Reference

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| Database connection failed | PostgreSQL not running | `docker-compose up -d db` |
| 401 Unauthorized | Invalid/expired JWT | Re-login or refresh token |
| Schema does not exist | Auto-setup failed | Check logs, verify permissions |
| Port 8000 in use | Another process running | Kill process or use different port |
| Migration failed | SQL syntax error | Check migration files, verify DB connection |
| Admin user not created | Seeding failed | Check logs, manually seed if needed |

---

## Database Issues

### Issue: Database "systemdb" Does Not Exist

**Error**:
```
asyncpg.exceptions.InvalidCatalogNameError: database "systemdb" does not exist
```

**Cause**: Backend auto-setup is failing to connect to PostgreSQL server.

**Solution**:

1. **Check PostgreSQL is running**:
   ```bash
   docker-compose ps db
   # Or for local PostgreSQL
   pg_isready -h localhost -p 5432
   ```

2. **Verify connection string**:
   ```bash
   echo $DATABASE_URL
   # Should be: postgresql+asyncpg://postgres:adminPassw0rd@localhost:5432/systemdb
   ```

3. **Test connection to PostgreSQL server**:
   ```bash
   psql -h localhost -U postgres -d postgres
   # Enter password: adminPassw0rd
   ```

4. **Manually create database** (if auto-setup fails):
   ```bash
   psql -h localhost -U postgres
   CREATE DATABASE systemdb;
   \q
   ```

5. **Restart backend**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

---

### Issue: Schema "systemdb" Does Not Exist

**Error**:
```
sqlalchemy.exc.ProgrammingError: schema "systemdb" does not exist
```

**Cause**: Schema not created during setup.

**Solution**:

1. **Check if schema exists**:
   ```bash
   psql -h localhost -U postgres -d systemdb
   \dn
   # Should list "systemdb" schema
   ```

2. **Create schema manually**:
   ```sql
   CREATE SCHEMA IF NOT EXISTS systemdb;
   GRANT ALL PRIVILEGES ON SCHEMA systemdb TO postgres;
   ```

3. **Check migration ran**:
   ```bash
   docker-compose logs api | grep "Running database migrations"
   ```

4. **Manually run migration**:
   ```bash
   psql -h localhost -U postgres -d systemdb -f app/db/migrations/000_create_users_table.sql
   ```

---

### Issue: Permission Denied for Schema

**Error**:
```
sqlalchemy.exc.ProgrammingError: permission denied for schema systemdb
```

**Cause**: Database user lacks permissions.

**Solution**:

1. **Grant permissions**:
   ```sql
   -- Connect as superuser
   psql -h localhost -U postgres -d systemdb
   
   -- Grant all permissions
   GRANT ALL PRIVILEGES ON SCHEMA systemdb TO postgres;
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA systemdb TO postgres;
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA systemdb TO postgres;
   ```

2. **Verify permissions**:
   ```sql
   \dn+ systemdb
   ```

---

### Issue: Tables Not Created

**Error**:
```
relation "systemdb.users" does not exist
```

**Cause**: Migrations didn't run or failed.

**Solution**:

1. **Check migration logs**:
   ```bash
   docker-compose logs api | grep -A 10 "Running database migrations"
   ```

2. **Verify migration files exist**:
   ```bash
   ls -la app/db/migrations/
   # Should see: 000_create_users_table.sql, 001_create_tables.sql, 002_seed_data.sql
   ```

3. **Manually run migrations**:
   ```bash
   psql -h localhost -U postgres -d systemdb
   \i app/db/migrations/000_create_users_table.sql
   \i app/db/migrations/001_create_tables.sql
   \i app/db/migrations/002_seed_data.sql
   ```

4. **Verify tables created**:
   ```bash
   psql -h localhost -U postgres -d systemdb
   \dt systemdb.*
   ```

---

### Issue: Admin User Not Created

**Error**: Login fails with "Invalid credentials" for admin@example.com

**Cause**: Seeding failed or admin user was deleted.

**Solution**:

1. **Check seeding logs**:
   ```bash
   docker-compose logs api | grep "Admin user"
   # Should see: "Admin user seeding completed"
   ```

2. **Verify admin user exists**:
   ```bash
   psql -h localhost -U postgres -d systemdb
   SELECT id, email, role FROM systemdb.users WHERE email = 'admin@example.com';
   ```

3. **Manually create admin user**:
   ```bash
   python -c "
   from app.db.seed import seed_admin_user
   from app.db.database import AsyncSessionLocal
   import asyncio
   asyncio.run(seed_admin_user(AsyncSessionLocal()))
   "
   ```

4. **Check password in .env**:
   ```bash
   grep SEED_ADMIN_PASSWORD .env
   # Should be: SEED_ADMIN_PASSWORD=ChangeMe123!
   ```

---

## Authentication Issues

### Issue: 401 Unauthorized on Login

**Error**:
```json
{
  "detail": "Invalid credentials"
}
```

**Cause**: Wrong email or password.

**Solution**:

1. **Verify credentials**:
   - Default admin: `admin@example.com` / `ChangeMe123!`
   - Check case sensitivity

2. **Check user exists**:
   ```sql
   SELECT email, role FROM systemdb.users WHERE email = 'admin@example.com';
   ```

3. **Reset admin password** (if needed):
   ```bash
   python -c "
   from app.db.seed import hash_password
   from app.db.database import engine
   from sqlalchemy import text
   
   new_hash = hash_password('NewPassword123!')
   with engine.connect() as conn:
       conn.execute(text('''
           UPDATE systemdb.users 
           SET password_hash = :hash 
           WHERE email = 'admin@example.com'
       '''), {'hash': new_hash})
       conn.commit()
   "
   ```

---

### Issue: 401 Unauthorized on Protected Endpoints

**Error**:
```json
{
  "detail": "Invalid or expired token"
}
```

**Cause**: JWT token is invalid, expired, or missing.

**Solution**:

1. **Verify token is included**:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/chat
   ```

2. **Check token format**:
   - Must be: `Authorization: Bearer <token>`
   - No extra spaces or quotes

3. **Verify token not expired**:
   ```bash
   # Decode JWT (use https://jwt.io)
   # Check 'exp' claim (Unix timestamp)
   ```

4. **Get new token**:
   ```bash
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@example.com","password":"ChangeMe123!"}'
   ```

5. **Refresh token** (if expired):
   ```bash
   curl -X POST http://localhost:8000/api/auth/refresh \
     -H "Authorization: Bearer YOUR_OLD_TOKEN"
   ```

---

### Issue: JWT_SECRET_KEY Not Set

**Error**:
```
pydantic_settings.sources.SettingsError: Field "JWT_SECRET_KEY" is required
```

**Cause**: Missing JWT_SECRET_KEY in .env file.

**Solution**:

1. **Add to .env**:
   ```env
   JWT_SECRET_KEY=your-super-secret-key-min-32-chars-long
   ```

2. **Generate secure key**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Restart backend** after updating .env.

---

## Session Issues

### Issue: Invalid Session ID Format

**Error**:
```json
{
  "detail": "Invalid session ID format. Must be: chat_[a-f0-9]{16}"
}
```

**Cause**: Session ID doesn't match required pattern.

**Solution**:

1. **Use correct format**:
   ```typescript
   // Correct
   const sessionId = `chat_abc123def456789`;
   
   // Generate random
   const sessionId = `chat_${Array.from({length: 16}, () => 
     Math.floor(Math.random() * 16).toString(16)
   ).join('')}`;
   ```

2. **Pattern**: `^chat_[a-f0-9]{16}$`
   - Must start with `chat_`
   - Followed by exactly 16 lowercase hex characters (0-9, a-f)
   - No uppercase letters
   - No special characters

3. **Examples**:
   - ✅ `chat_abc123def456789`
   - ✅ `chat_1234567890abcdef`
   - ❌ `chat_ABC123` (uppercase)
   - ❌ `session_123` (wrong prefix)
   - ❌ `chat_123` (too short)

---

### Issue: Session Not Found

**Error**:
```json
{
  "detail": "Session not found"
}
```

**Cause**: Session doesn't exist or belongs to another user.

**Solution**:

1. **Create session first**:
   ```bash
   curl -X POST http://localhost:8000/api/session \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"session_id": "chat_abc123def456789"}'
   ```

2. **Verify session exists**:
   ```bash
   curl -X GET http://localhost:8000/api/session/chat_abc123def456789 \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

3. **Check session ownership**:
   - Sessions are user-specific
   - Cannot access another user's session

---

### Issue: Session Lost After Restart

**Cause**: In-memory session storage (by design for development).

**Solution**:

1. **For development**: Accept that sessions are lost on restart.

2. **For production**: Configure Redis:
   ```env
   REDIS_URL=redis://localhost:6379
   ```

3. **See**: `docs/REDIS-MIGRATION.md` for migration guide.

---

## Application Issues

### Issue: Port 8000 Already in Use

**Error**:
```
OSError: [Errno 48] Address already in use
```

**Cause**: Another process is using port 8000.

**Solution**:

1. **Find process using port 8000**:
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :8000
   ```

2. **Kill process**:
   ```bash
   # Windows
   taskkill /PID <PID> /F
   
   # Linux/Mac
   kill -9 <PID>
   ```

3. **Or use different port**:
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

---

### Issue: ModuleNotFoundError

**Error**:
```
ModuleNotFoundError: No module named 'fastapi'
```

**Cause**: Dependencies not installed.

**Solution**:

1. **Install dependencies**:
   ```bash
   pip install -e .
   ```

2. **Or install specific package**:
   ```bash
   pip install fastapi uvicorn asyncpg sqlalchemy
   ```

3. **Verify installation**:
   ```bash
   python -c "import fastapi; print(fastapi.__version__)"
   ```

---

### Issue: CORS Error

**Error**:
```
Access to fetch at 'http://localhost:8000' has been blocked by CORS policy
```

**Cause**: Frontend origin not allowed in backend CORS configuration.

**Solution**:

1. **Update .env**:
   ```env
   FRONTEND_URL=http://localhost:5174
   ALLOWED_ORIGINS=http://localhost:5174,http://localhost:3000
   ```

2. **Restart backend**.

3. **Verify CORS headers**:
   ```bash
   curl -I http://localhost:8000/health
   # Should see: Access-Control-Allow-Origin: http://localhost:5174
   ```

---

### Issue: OpenAI API Error

**Error**:
```
openai.APIStatusError: 401 Incorrect API key
```

**Cause**: Invalid or missing OpenAI API key.

**Solution**:

1. **Check API key in .env**:
   ```bash
   grep OPENAI_API_KEY .env
   ```

2. **Verify key format**:
   - Should start with `sk-proj-` or `sk-`
   - No extra spaces or quotes

3. **Test API key**:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer sk-..."
   ```

4. **Get new key**: https://platform.openai.com/api-keys

---

## Docker Issues

### Issue: Docker Container Won't Start

**Error**:
```
Error: Cannot start service api: ...
```

**Cause**: Various Docker configuration issues.

**Solution**:

1. **Check Docker is running**:
   ```bash
   docker ps
   ```

2. **View container logs**:
   ```bash
   docker-compose logs api
   ```

3. **Rebuild containers**:
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

4. **Check .env file**:
   - Ensure all required variables are set
   - No extra spaces or quotes

---

### Issue: Database Container Not Healthy

**Error**:
```
db container is not healthy
```

**Cause**: PostgreSQL failed to start.

**Solution**:

1. **Check container logs**:
   ```bash
   docker-compose logs db
   ```

2. **Verify volume permissions**:
   ```bash
   docker-compose down -v  # WARNING: Deletes data!
   docker-compose up -d db
   ```

3. **Check port conflict**:
   ```bash
   netstat -ano | findstr :5432
   ```

---

## Performance Issues

### Issue: Slow Database Queries

**Symptoms**: High latency on API responses.

**Solution**:

1. **Check database indexes**:
   ```sql
   \di systemdb.*
   # Should see idx_users_email
   ```

2. **Enable query logging**:
   ```sql
   ALTER SYSTEM SET log_min_duration_statement = 1000;
   SELECT pg_reload_conf();
   ```

3. **Check connection pool**:
   - Default: 10 connections
   - Increase if needed in DATABASE_URL

4. **Use Redis for sessions** (production):
   ```env
   REDIS_URL=redis://localhost:6379
   ```

---

### Issue: High Memory Usage

**Symptoms**: Container using >512MB RAM.

**Solution**:

1. **Check for memory leaks**:
   ```bash
   docker stats
   ```

2. **Limit container memory**:
   ```yaml
   # docker-compose.yml
   services:
     api:
       deploy:
         resources:
           limits:
             memory: 512M
   ```

3. **Enable garbage collection**:
   ```python
   # In app/main.py
   import gc
   gc.collect()
   ```

---

## Getting Help

### Check Logs

```bash
# Application logs
docker-compose logs -f api

# Database logs
docker-compose logs -f db

# Filter by keyword
docker-compose logs api | grep "ERROR"
```

### Enable Debug Mode

```env
# In .env
DEBUG=true
```

This enables:
- Detailed error messages
- SQL query logging
- Verbose startup logs

### Contact Support

- **GitHub Issues**: https://github.com/your-repo/multi-agent-coach/issues
- **Documentation**: See all files in `docs/` directory
- **API Docs**: http://localhost:8000/docs (when running)

---

## Common Commands

### Database Operations

```bash
# Connect to database
psql -h localhost -U postgres -d systemdb

# Backup database
pg_dump -U postgres systemdb > backup.sql

# Restore database
psql -U postgres -d systemdb < backup.sql

# Drop and recreate
psql -U postgres -c "DROP DATABASE IF EXISTS systemdb;"
psql -U postgres -c "CREATE DATABASE systemdb;"
```

### Docker Operations

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f api

# Restart specific service
docker-compose restart api

# Rebuild containers
docker-compose build --no-cache

# Clean up everything
docker-compose down -v
```

### Application Operations

```bash
# Start backend
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v

# Check dependencies
pip list

# Update dependencies
pip install -e . --upgrade
```

---

**End of Troubleshooting Guide**
