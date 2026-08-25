# Deployment Checklist

**Version**: 1.0.0  
**Last Updated**: 2026-08-24

---

## Pre-Deployment Checklist

### Development Environment

- [ ] All local tests passing
- [ ] Code formatted (ruff, prettier)
- [ ] No TypeScript errors
- [ ] No Python linting errors
- [ ] Environment variables documented
- [ ] `.env.example` up to date
- [ ] README.md reflects current setup

### Code Quality

- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] API endpoints documented
- [ ] Error handling implemented
- [ ] Logging configured
- [ ] Health check endpoint working

### Security

- [ ] No hardcoded secrets in code
- [ ] JWT_SECRET_KEY is secure (min 32 chars)
- [ ] Database passwords rotated
- [ ] CORS configured for production domain
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (frontend escaping)

### Dependencies

- [ ] All dependencies up to date
- [ ] Security vulnerabilities scanned (`pip audit`, `npm audit`)
- [ ] Unused dependencies removed
- [ ] Dependency versions pinned

---

## Local Development Deployment

### Prerequisites

- [ ] Docker installed
- [ ] Docker Compose installed
- [ ] PostgreSQL installed (if not using Docker)
- [ ] Python 3.12+ installed
- [ ] Node.js 18+ installed
- [ ] Git installed

### Backend Setup

- [ ] Clone repository
- [ ] Create virtual environment
- [ ] Install dependencies: `pip install -e .`
- [ ] Copy `.env.example` to `.env`
- [ ] Configure environment variables:
  - [ ] `DATABASE_URL`
  - [ ] `JWT_SECRET_KEY`
  - [ ] `OPENAI_API_KEY`
  - [ ] `FRONTEND_URL`
- [ ] Start database: `docker-compose up -d db`
- [ ] Verify database connection: `psql $DATABASE_URL`
- [ ] Start backend: `uvicorn app.main:app --reload --port 8000`
- [ ] Verify health check: `curl http://localhost:8000/health`

### Frontend Setup

- [ ] Navigate to `frontend/` directory
- [ ] Install dependencies: `npm install`
- [ ] Create `.env` file with `VITE_API_BASE_URL=http://localhost:8000/api`
- [ ] Start development server: `npm run dev`
- [ ] Verify frontend loads: `http://localhost:5174`

### Testing

- [ ] Register new user
- [ ] Login with credentials
- [ ] JWT token stored in localStorage
- [ ] Send chat message
- [ ] Receive response
- [ ] Session persists across page reload
- [ ] Logout clears token
- [ ] Error handling works (401, 500)

---

## Staging Environment

### Infrastructure

- [ ] Staging VPC configured
- [ ] Security groups configured
- [ ] RDS PostgreSQL instance created
- [ ] ElastiCache Redis cluster created
- [ ] S3 bucket created
- [ ] ECR repository created
- [ ] IAM roles configured

### Backend Deployment

- [ ] Build Docker image: `docker build -t multi-agent-coach-api:staging .`
- [ ] Tag for ECR
- [ ] Push to ECR
- [ ] Update ECS task definition
- [ ] Deploy to ECS
- [ ] Verify service is running
- [ ] Check CloudWatch logs
- [ ] Verify health check passing

### Database Migration

- [ ] Run migrations: `python -m app.db.database`
- [ ] Verify tables created
- [ ] Verify indexes created
- [ ] Seed admin user
- [ ] Test database connection from ECS

### Frontend Deployment

- [ ] Update API URL to staging backend
- [ ] Build frontend: `npm run build`
- [ ] Deploy to S3/CloudFront
- [ ] Configure custom domain (if applicable)
- [ ] Enable HTTPS
- [ ] Test frontend connectivity

### Testing

- [ ] Smoke tests passing
- [ ] Integration tests passing
- [ ] Load testing (10 concurrent users)
- [ ] Performance baseline established
- [ ] Error rates < 1%
- [ ] Latency p95 < 500ms

---

## Production Deployment

### Infrastructure (AWS)

- [ ] Production VPC configured
- [ ] Public and private subnets
- [ ] NAT Gateway configured
- [ ] Internet Gateway configured
- [ ] Route tables configured

### Security

- [ ] Security groups configured:
  - [ ] ALB: Allow 80, 443 from 0.0.0.0/0
  - [ ] ECS: Allow 8000 from ALB
  - [ ] RDS: Allow 5432 from ECS
  - [ ] Redis: Allow 6379 from ECS
- [ ] Network ACLs configured
- [ ] VPC flow logs enabled
- [ ] AWS WAF configured (optional)

### Database (RDS)

- [ ] RDS instance created (Multi-AZ)
- [ ] Automated backups enabled (7-day retention)
- [ ] Encryption at rest enabled
- [ ] Parameter group configured
- [ ] Subnet group configured
- [ ] Security group configured
- [ ] Initial database created: `systemdb`
- [ ] Migrations run successfully
- [ ] Read replica configured (optional)

### Cache (ElastiCache)

- [ ] Redis cluster created
- [ ] Multi-AZ enabled
- [ ] Encryption in transit enabled
- [ ] Encryption at rest enabled
- [ ] Subnet group configured
- [ ] Security group configured
- [ ] Redis AUTH configured

### Storage (S3)

- [ ] S3 bucket created
- [ ] Server-side encryption enabled
- [ ] Versioning enabled
- [ ] Public access blocked
- [ ] Lifecycle policies configured
- [ ] CORS configured for backend
- [ ] Bucket policy configured

### Compute (ECS Fargate)

- [ ] ECS cluster created
- [ ] Task definition registered:
  - [ ] CPU: 1024
  - [ ] Memory: 2048
  - [ ] Container port: 8000
  - [ ] Health check configured
  - [ ] Log configuration (CloudWatch)
  - [ ] Environment variables from Secrets Manager
- [ ] Service created:
  - [ ] Desired count: 2 (minimum)
  - [ ] Load balancer attached
  - [ ] Auto-scaling configured
- [ ] Auto-scaling policies:
  - [ ] Scale up at 70% CPU
  - [ ] Scale down at 30% CPU
  - [ ] Min tasks: 2
  - [ ] Max tasks: 10

### Load Balancer (ALB)

- [ ] ALB created (internet-facing)
- [ ] Target group created:
  - [ ] Health check path: `/health`
  - [ ] Health check interval: 30s
  - [ ] Unhealthy threshold: 3
- [ ] Listener configured:
  - [ ] HTTP (80) → HTTPS redirect
  - [ ] HTTPS (443) → Forward to target group
- [ ] SSL certificate from ACM
- [ ] Access logs enabled

### Secrets Management

- [ ] Secrets Manager secret created
- [ ] Secrets include:
  - [ ] `DATABASE_URL`
  - [ ] `JWT_SECRET_KEY`
  - [ ] `OPENAI_API_KEY`
  - [ ] `REDIS_URL`
  - [ ] `AWS_ACCESS_KEY_ID`
  - [ ] `AWS_SECRET_ACCESS_KEY`
- [ ] ECS task role has access to secrets
- [ ] Secret rotation configured (optional)

### Monitoring (CloudWatch)

- [ ] Log groups created:
  - [ ] `/ecs/multi-agent-coach-api`
  - [ ] `/ecs/multi-agent-coach-db`
- [ ] Metrics enabled
- [ ] Dashboards created
- [ ] Alarms configured:
  - [ ] High CPU (>80% for 5 min)
  - [ ] High memory (>80% for 5 min)
  - [ ] High error rate (>5% for 5 min)
  - [ ] High latency (p95 >1s for 5 min)
  - [ ] RDS connections (>100)
  - [ ] RDS free storage (<10GB)
- [ ] SNS topic for alerts
- [ ] PagerDuty integration (optional)

### CI/CD Pipeline

- [ ] GitHub Actions workflow created
- [ ] Build stage:
  - [ ] Lint code
  - [ ] Run tests
  - [ ] Build Docker image
  - [ ] Scan for vulnerabilities
- [ ] Deploy stage:
  - [ ] Push to ECR
  - [ ] Update ECS task definition
  - [ ] Deploy to ECS
  - [ ] Wait for deployment
  - [ ] Run smoke tests
- [ ] Rollback strategy:
  - [ ] Automatic rollback on failure
  - [ ] Previous task definition retained

### DNS & Domain

- [ ] Domain registered
- [ ] Route53 hosted zone created
- [ ] SSL certificate requested (ACM)
- [ ] DNS records configured:
  - [ ] A record → ALB
  - [ ] CNAME for www
- [ ] HTTPS redirect configured

### Performance Optimization

- [ ] Database indexes verified
- [ ] Query performance optimized
- [ ] Caching strategy implemented
- [ ] CDN configured for static assets
- [ ] Gzip compression enabled
- [ ] Connection pooling configured
- [ ] Load testing completed (100+ concurrent users)

### Security Hardening

- [ ] AWS Config enabled
- [ ] AWS Security Hub enabled
- [ ] AWS GuardDuty enabled
- [ ] AWS Inspector enabled (optional)
- [ ] Penetration testing completed
- [ ] OWASP Top 10 reviewed
- [ ] Security audit completed

### Compliance & Documentation

- [ ] Privacy policy updated
- [ ] Terms of service updated
- [ ] API documentation published
- [ ] Runbook created
- [ ] Incident response plan documented
- [ ] On-call rotation configured

---

## Post-Deployment Checklist

### Immediate (First Hour)

- [ ] Health check passing
- [ ] All services running
- [ ] No errors in logs
- [ ] Metrics flowing to CloudWatch
- [ ] Alarms configured and not firing
- [ ] Database migrations successful
- [ ] Admin user created
- [ ] Can login to application

### Short-Term (First Day)

- [ ] Smoke tests passing
- [ ] Real user monitoring enabled
- [ ] Error tracking configured (Sentry, etc.)
- [ ] Backup verification completed
- [ ] Disaster recovery tested
- [ ] Performance baseline established
- [ ] User acceptance testing completed

### Ongoing (Weekly/Monthly)

- [ ] Review CloudWatch metrics
- [ ] Check error rates
- [ ] Monitor database performance
- [ ] Review access logs
- [ ] Update dependencies
- [ ] Security patches applied
- [ ] Backup restoration tested
- [ ] Cost optimization reviewed

---

## Rollback Plan

### Trigger Conditions

- Critical bug in production
- Performance degradation > 50%
- Error rate > 10%
- Security vulnerability discovered
- Data corruption detected

### Rollback Steps

1. **ECS Rollback**:
   ```bash
   # Update service to previous task definition
   aws ecs update-service \
     --cluster multi-agent-coach-cluster \
     --service multi-agent-coach-service \
     --task-definition multi-agent-coach-api:PREVIOUS_REVISION
   ```

2. **Database Rollback**:
   ```bash
   # Restore from snapshot (if needed)
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier multi-agent-coach-db-restored \
     --db-snapshot-identifier pre-deployment-snapshot
   ```

3. **Frontend Rollback**:
   ```bash
   # Deploy previous version from S3 versioning
   aws s3api get-object-version \
     --bucket multi-agent-coach-frontend \
     --key index.html \
     --version-id PREVIOUS_VERSION_ID
   ```

4. **Communication**:
   - [ ] Notify stakeholders
   - [ ] Update status page
   - [ ] Document incident
   - [ ] Schedule post-mortem

---

## Cost Optimization

### Right-Sizing

- [ ] ECS tasks: Monitor actual CPU/memory usage
- [ ] RDS: Check if instance class can be reduced
- [ ] Redis: Evaluate node type
- [ ] Storage: Review S3 usage

### Reserved Instances

- [ ] RDS: Consider reserved instance for steady-state
- [ ] ElastiCache: Consider reserved nodes
- [ ] Savings Plans for ECS

### Auto-Scaling

- [ ] Scale down during off-peak hours
- [ ] Use spot instances for non-critical workloads
- [ ] Implement scheduled scaling

### Storage

- [ ] S3 lifecycle policies (transition to Glacier)
- [ ] Delete old Docker images from ECR
- [ ] Clean up old RDS snapshots
- [ ] Remove unused EBS volumes

---

## Estimated Costs (Monthly)

### Development

| Service | Configuration | Cost |
|---------|--------------|------|
| RDS | db.t3.micro | ~$15 |
| ElastiCache | cache.t3.micro | ~$10 |
| S3 | 10GB | ~$1 |
| **Total** | | **~$26/month** |

### Staging

| Service | Configuration | Cost |
|---------|--------------|------|
| ECS Fargate | 1 task, 0.5 vCPU, 1GB | ~$30 |
| RDS | db.t3.small | ~$30 |
| ElastiCache | cache.t3.small | ~$20 |
| S3 | 10GB | ~$1 |
| ALB | 1 load balancer | ~$20 |
| **Total** | | **~$101/month** |

### Production

| Service | Configuration | Cost |
|---------|--------------|------|
| ECS Fargate | 2 tasks, 1 vCPU, 2GB | ~$60 |
| RDS | db.t3.medium, Multi-AZ | ~$200 |
| ElastiCache | 2 nodes, cache.t3.medium | ~$100 |
| S3 | 100GB + requests | ~$5 |
| ALB | 1 load balancer | ~$20 |
| CloudWatch | Logs + metrics | ~$10 |
| Data transfer | ~100GB/month | ~$10 |
| **Total** | | **~$405/month** |

---

## Support Contacts

### Internal

- **DevOps Lead**: [Name] - [Email]
- **Backend Lead**: [Name] - [Email]
- **Frontend Lead**: [Name] - [Email]
- **On-Call**: [PagerDuty Link]

### External

- **AWS Support**: [Support Plan Level]
- **Database Support**: [Vendor Contact]
- **Security Team**: [Email]

---

## Appendix

### Useful Commands

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster multi-agent-coach-cluster \
  --services multi-agent-coach-service

# View CloudWatch logs
aws logs tail /ecs/multi-agent-coach-api --follow

# Check RDS status
aws rds describe-db-instances \
  --db-instance-identifier multi-agent-coach-db

# Get ECS task logs
aws logs get-log-events \
  --log-group-name /ecs/multi-agent-coach-api \
  --log-stream-name <stream-name>

# Restart ECS service
aws ecs update-service \
  --cluster multi-agent-coach-cluster \
  --service multi-agent-coach-service \
  --force-new-deployment
```

### Monitoring Dashboard

Create CloudWatch dashboard with:
- ECS CPU utilization
- ECS memory utilization
- RDS CPU utilization
- RDS database connections
- RDS free storage
- ElastiCache CPU utilization
- ElastiCache cache hit rate
- ALB request count
- ALB target response time
- API error rate (5xx)
- API latency (p50, p95, p99)

---

**End of Deployment Checklist**
