# Multi-Agent Fitness Coach - AWS Production Deployment

Complete guide for deploying Multi-Agent Fitness Coach with Docker Compose or to AWS production.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Docker Compose Stack Deployment](#docker-compose-stack-deployment)
3. [Prerequisites](#prerequisites)
4. [Infrastructure Setup](#infrastructure-setup)
5. [PostgreSQL Container Deployment](#postgresql-container-deployment)
6. [Backend Deployment](#backend-deployment)
7. [Frontend Deployment](#frontend-deployment)
8. [Configuration](#configuration)
9. [Monitoring & Operations](#monitoring--operations)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                 AWS Cloud                            │
│                                                      │
│  ┌─────────────┐                                    │
│  │  ALB        │  (Application Load Balancer)       │
│  │  (HTTPS)    │  - SSL/TLS termination             │
│  └──────┬──────┘  - Health checks                   │
│         │                                           │
│  ┌──────▼──────────────────────┐                   │
│  │   ECS Fargate Tasks         │                   │
│  │   - Backend API (Port 8000) │                   │
│  │   - Auto-scaling (2-10)     │                   │
│  └──────┬──────────────────────┘                   │
│         │                                           │
│    ┌────┴────┬──────────────┬──────────────┐      │
│    │         │              │              │      │
│ ┌──▼──┐ ┌───▼────┐   ┌─────▼────┐ ┌──────▼────┐ │
│ │ RDS │ │Elasti  │   │   S3     │ │  Secrets  │ │
│ │PostgreSQL│Cache│   │  Bucket  │ │  Manager  │ │
│ │       │ │Redis │   │          │ │           │ │
│ └──────┘ └───────┘   └──────────┘ └───────────┘ │
└─────────────────────────────────────────────────┘
```

---

## Docker Compose Stack Deployment

Use the repository Compose definition to build and start the containerized application stack, including the main API and private agents. This is separate from the local-only workflow in [README.md](README.md).

### Prerequisites

- Docker Desktop or Docker Engine with the Compose plugin running.
- Required secrets configured in the shell environment or `C:\dev\multi-agent-coach\.env`; at minimum, provide a valid `OPENAI_API_KEY` if enabled by your configuration. Do not commit real keys.

### Start the complete stack

From `C:\dev\multi-agent-coach`:

```powershell
docker compose up --build
```

The Compose stack starts:

- PostgreSQL (`db`) with persistent `postgres_data` storage.
- Redis (`redis`) with persistent `redis_data` storage.
- A one-shot `migrations` job.
- The main FastAPI service (`api`) on <http://localhost:8000>.
- The private Recovery Agent (`recovery-agent`) bound to `127.0.0.1:8001`.
- The private Nutrition Agent (`nutrition-agent`) bound to `127.0.0.1:8003`.

The React frontend is not part of `docker-compose.yml`; build or deploy it separately with its API base URL pointed at the main API.

### Migration and startup ordering

Compose owns the startup sequence:

1. PostgreSQL must pass its health check.
2. The `migrations` service runs `python -m app.db.migrate` against PostgreSQL.
3. The main API and Nutrition Agent wait for that job to exit successfully.
4. Runtime services perform connection and schema-readiness validation only; they do not run migrations, seed users, or execute schema DDL.

If the migration job fails, inspect its logs and correct the database or migration problem before starting the runtime services:

```powershell
docker compose logs migrations
docker compose logs api nutrition-agent recovery-agent
```

### Verify and operate the stack

```powershell
# Follow service logs.
docker compose logs -f api nutrition-agent recovery-agent

# Check service state.
docker compose ps

# Stop containers while retaining PostgreSQL and Redis volumes.
docker compose down

# Remove containers and persistent volumes. This deletes Compose-managed data.
docker compose down --volumes --remove-orphans
```

Check main-API health at <http://localhost:8000/health/live> and readiness at <http://localhost:8000/health/ready>. The Nutrition Agent is private: do not publish it through browser-facing ingress or expose its internal-service token.

### Compose deployment smoke test

The opt-in smoke test creates an isolated Compose project, waits for the services, checks that migrations succeed, checks API and Nutrition-Agent readiness, and removes the resources it created:

```powershell
.\scripts\test-compose-deployment.ps1
```

---

## Prerequisites

### Required Tools
- AWS CLI configured with appropriate permissions
- Docker installed locally
- AWS account with IAM permissions for:
  - ECS/Fargate
  - RDS
  - ElastiCache
  - S3
  - Secrets Manager
  - Application Load Balancer

### Estimated Costs (Monthly)

| Service | Configuration | Cost |
|---------|--------------|------|
| ECS Fargate | 2 tasks, 1 vCPU, 2GB | ~$60 |
| RDS PostgreSQL | db.t3.medium, Multi-AZ | ~$200 |
| ElastiCache Redis | 2 nodes, cache.t3.medium | ~$100 |
| S3 | 100GB storage | ~$5 |
| ALB | 1 load balancer | ~$20 |
| **Total** | | **~$405/month** |

---

## Infrastructure Setup

### Step 1: Create VPC Resources

```bash
# Create VPC
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=multi-agent-coach-vpc}]'

# Create public subnets (for ALB)
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.1.0/24 --availability-zone us-east-1a
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.2.0/24 --availability-zone us-east-1b

# Create private subnets (for ECS, RDS, Redis)
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.10.0/24 --availability-zone us-east-1a
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.11.0/24 --availability-zone us-east-1b

# Create Internet Gateway
aws ec2 create-internet-gateway
aws ec2 attach-internet-gateway --vpc-id vpc-xxx --internet-gateway-id igw-xxx
```

### Step 2: Create Security Groups

```bash
# ALB Security Group (allow HTTP/HTTPS from internet)
aws ec2 create-security-group \
  --group-name multi-agent-coach-alb-sg \
  --description "Security group for ALB" \
  --vpc-id vpc-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-alb \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# ECS Security Group (allow 8000 from ALB)
aws ec2 create-security-group \
  --group-name multi-agent-coach-ecs-sg \
  --description "Security group for ECS tasks" \
  --vpc-id vpc-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-ecs \
  --protocol tcp \
  --port 8000 \
  --source-group sg-alb

# RDS Security Group (allow 5432 from ECS)
aws ec2 create-security-group \
  --group-name multi-agent-coach-rds-sg \
  --description "Security group for RDS" \
  --vpc-id vpc-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-rds \
  --protocol tcp \
  --port 5432 \
  --source-group sg-ecs
```

---

## PostgreSQL Container Deployment

### Option A: Using Amazon RDS (Recommended for Production)

```bash
# Create RDS PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier multi-agent-coach-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 16.2 \
  --master-username postgres \
  --master-user-password YOUR_SECURE_PASSWORD \
  --allocated-storage 100 \
  --storage-type gp3 \
  --db-subnet-group-name multi-agent-coach-subnet \
  --vpc-security-group-ids sg-rds \
  --multi-az \
  --backup-retention-period 7 \
  --tags Key=Project,Value=MultiAgentCoach

# Wait for instance to be available
aws rds wait db-instance-available --db-instance-identifier multi-agent-coach-db
```

**RDS Configuration:**
- Engine: PostgreSQL 16.2
- Instance Class: db.t3.medium (scale as needed)
- Storage: 100 GB GP3
- Multi-AZ: Enabled for high availability
- Backup retention: 7 days
- Auto minor version upgrade: Enabled

### Option B: Using PostgreSQL Container on ECS

For cost optimization, you can run PostgreSQL in a container on ECS:

```yaml
# postgres-task-definition.json
{
  "family": "postgres",
  "containerDefinitions": [
    {
      "name": "postgres",
      "image": "postgres:16-alpine",
      "portMappings": [
        {
          "containerPort": 5432,
          "hostPort": 5432,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "POSTGRES_PASSWORD",
          "value": "YOUR_SECURE_PASSWORD"
        },
        {
          "name": "POSTGRES_DB",
          "value": "systemdb"
        }
      ],
      "mountPoints": [
        {
          "sourceVolume": "postgres-data",
          "containerPath": "/var/lib/postgresql/data"
        }
      ]
    }
  ],
  "volumes": [
    {
      "name": "postgres-data",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-xxx",
        "rootDirectory": "/postgres"
      }
    }
  ]
}
```

**⚠️ Warning:** Running PostgreSQL in containers requires careful consideration of:
- Data persistence (use EFS volumes)
- Backup strategy
- High availability
- Performance tuning

**Recommended only for:**
- Development/staging environments
- Cost-constrained projects
- Teams with strong DevOps capabilities

### Step 3: Create Database Schema

Once RDS/PostgreSQL is running:

```bash
# Connect to database
psql -h multi-agent-coach-db.xxx.us-east-1.rds.amazonaws.com \
     -U postgres \
     -d postgres

# Create database
CREATE DATABASE systemdb;

# Connect to systemdb
\c systemdb

# Create schema
CREATE SCHEMA systemdb;

# Run migrations
\i /path/to/app/db/migrations/000_create_users_table.sql
\i /path/to/app/db/migrations/001_create_tables.sql
```

---

## Backend Deployment

### Step 1: Create ECR Repository

```bash
aws ecr create-repository \
  --repository-name multi-agent-coach-api \
  --image-scanning-configuration scanOnPush=true \
  --image-tag-mutability IMMUTABLE

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

### Step 2: Build and Push Docker Image

```bash
# Build image
docker build -t multi-agent-coach-api:latest .

# Tag for ECR
docker tag multi-agent-coach-api:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/multi-agent-coach-api:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/multi-agent-coach-api:latest
```

### Step 3: Store Secrets in AWS Secrets Manager

```bash
aws secretsmanager create-secret \
  --name multi-agent-coach/prod \
  --secret-string '{
    "DATABASE_URL": "postgresql+asyncpg://postgres:PASSWORD@multi-agent-coach-db.xxx.us-east-1.rds.amazonaws.com:5432/systemdb",
    "JWT_SECRET_KEY": "your-super-secret-key-min-32-chars",
    "OPENAI_API_KEY": "sk-proj-...",
    "REDIS_URL": "redis://multi-agent-coach-redis.xxx.ng.0001.use1.cache.amazonaws.com:6379",
    "AWS_REGION": "us-east-1",
    "S3_BUCKET": "multi-agent-coach-chat-history"
  }'
```

### Step 4: Create S3 Bucket for Chat History

```bash
aws s3api create-bucket \
  --bucket multi-agent-coach-chat-history \
  --region us-east-1

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket multi-agent-coach-chat-history \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket multi-agent-coach-chat-history \
  --public-access-block-configuration '{
    "BlockPublicAcls": true,
    "IgnorePublicAcls": true,
    "BlockPublicPolicy": true,
    "RestrictPublicBuckets": true
  }'
```

### Step 5: Create ElastiCache Redis Cluster

```bash
# Create Redis subnet group
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name multi-agent-coach-redis \
  --cache-subnet-group-description "Redis subnet group" \
  --subnet-ids subnet-xxx subnet-yyy

# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id multi-agent-coach-redis \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.t3.medium \
  --num-cache-nodes 2 \
  --cache-subnet-group-name multi-agent-coach-redis \
  --security-group-ids sg-redis \
  --snapshot-retention-limit 7
```

### Step 6: Create ECS Task Definition

```bash
cat > task-definition.json << EOF
{
  "family": "multi-agent-coach-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/multi-agent-coach-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        { "name": "APP_NAME", "value": "Multi-Agent Coach API" },
        { "name": "DEBUG", "value": "false" }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:multi-agent-coach/prod:secret-id::DATABASE_URL"
        },
        {
          "name": "JWT_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:multi-agent-coach/prod:secret-id::JWT_SECRET_KEY"
        },
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:multi-agent-coach/prod:secret-id::OPENAI_API_KEY"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/multi-agent-coach-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF

# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

### Step 7: Create ECS Service

```bash
# Create cluster
aws ecs create-cluster --cluster-name multi-agent-coach-cluster

# Create service
aws ecs create-service \
  --cluster multi-agent-coach-cluster \
  --service-name multi-agent-coach-service \
  --task-definition multi-agent-coach-api \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-private-1", "subnet-private-2"],
      "securityGroups": ["sg-ecs"],
      "assignPublicIp": "DISABLED"
    }
  }' \
  --load-balancers '{
    "targetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:<account-id>:targetgroup/multi-agent-coach-tg/xxx",
    "containerName": "api",
    "containerPort": 8000
  }'
```

---

## Frontend Deployment

### Option A: S3 + CloudFront (Recommended)

```bash
# Build frontend
cd frontend
npm run build

# Create S3 bucket for frontend
aws s3api create-bucket \
  --bucket multi-agent-coach-frontend \
  --region us-east-1

# Upload build files
aws s3 sync build/ s3://multi-agent-coach-frontend/

# Configure bucket for static website hosting
aws s3 website s3://multi-agent-coach-frontend/ \
  --index-document index.html \
  --error-document index.html

# Create CloudFront distribution
aws cloudfront create-distribution \
  --origin-domain-name multi-agent-coach-frontend.s3.us-east-1.amazonaws.com \
  --default-root-object index.html
```

### Option B: Deploy to ECS with Backend

Include frontend build files in backend Docker image and serve via Nginx.

---

## Configuration

### Production Environment Variables

Store in AWS Secrets Manager:

```env
# Application
APP_NAME=Multi-Agent Coach API
APP_VERSION=1.0.0
DEBUG=false

# Database (RDS)
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@multi-agent-coach-db.xxx.us-east-1.rds.amazonaws.com:5432/systemdb
DATABASE_SCHEMA=systemdb

# JWT
JWT_SECRET_KEY=your-super-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# Session (Redis)
SESSION_EXPIRY_HOURS=24
REDIS_URL=redis://multi-agent-coach-redis.xxx.ng.0001.use1.cache.amazonaws.com:6379

# LLM
OPENAI_API_KEY=sk-proj-...
LLM_MODEL=gpt-5-nano

# AWS
AWS_REGION=us-east-1
S3_BUCKET=multi-agent-coach-chat-history
S3_PREFIX=chat-history

# CORS (Production domain)
FRONTEND_URL=https://your-domain.com
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

### Load Balancer Configuration

```bash
# Create target group
aws elbv2 create-target-group \
  --name multi-agent-coach-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3

# Create HTTPS listener (requires ACM certificate)
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:<account-id>:loadbalancer/app/multi-agent-coach-alb/xxx \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:us-east-1:<account-id>:certificate/xxx \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:<account-id>:targetgroup/multi-agent-coach-tg/xxx
```

---

## Monitoring & Operations

### CloudWatch Alarms

```bash
# High CPU utilization
aws cloudwatch put-metric-alarm \
  --alarm-name "MultiAgentCoach-HighCPU" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --dimensions Name=ClusterName,Value=multi-agent-coach-cluster Name=ServiceName,Value=multi-agent-coach-service \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:<account-id>:alerts

# High error rate
aws cloudwatch put-metric-alarm \
  --alarm-name "MultiAgentCoach-HighErrors" \
  --metric-name 5XXErrorCount \
  --namespace AWS/ApplicationELB \
  --dimensions Name=LoadBalancer,Value=arn:aws:elasticloadbalancing:us-east-1:<account-id>:loadbalancer/app/multi-agent-coach-alb/xxx \
  --statistic Sum \
  --period 60 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:<account-id>:alerts
```

### Logging

```bash
# View ECS task logs
aws logs tail /ecs/multi-agent-coach-api --follow

# View RDS logs
aws rds describe-db-log-files --db-instance-identifier multi-agent-coach-db
```

---

## Troubleshooting

### ECS Task Won't Start

```bash
# Describe task to see error
aws ecs describe-tasks \
  --cluster multi-agent-coach-cluster \
  --tasks <task-arn>

# Common issues:
# - IAM role permissions
# - VPC/subnet configuration
# - Resource limits
```

### Database Connection Failed

```bash
# Check security group allows ECS
aws ec2 describe-security-groups --group-ids sg-rds

# Verify connection string in Secrets Manager
aws secretsmanager get-secret-value --secret-id multi-agent-coach/prod

# Test connection from ECS task
aws ecs execute-command \
  --cluster multi-agent-coach-cluster \
  --task <task-id> \
  --container api \
  --interactive \
  --command "psql -h <rds-endpoint> -U postgres -d systemdb"
```

### High Latency

- Check ECS task and RDS are in same region
- Enable ElastiCache for session storage
- Use RDS Performance Insights
- Review CloudWatch metrics

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] Docker image builds successfully
- [ ] Security scan completed
- [ ] Database migrations tested

### Infrastructure
- [ ] VPC and subnets configured
- [ ] Security groups configured
- [ ] RDS PostgreSQL created
- [ ] ElastiCache Redis created
- [ ] S3 bucket created
- [ ] Secrets Manager configured

### Deployment
- [ ] Docker image pushed to ECR
- [ ] Task definition registered
- [ ] ECS service created
- [ ] Load balancer configured
- [ ] Health checks passing
- [ ] CloudWatch logs enabled

### Post-Deployment
- [ ] Smoke tests passing
- [ ] Database migrations run
- [ ] Admin user created
- [ ] Monitoring dashboards created
- [ ] Alerts configured

---

## Next Steps

### After Deployment
1. Configure custom domain with ACM certificate
2. Setup CI/CD pipeline (GitHub Actions, CodePipeline)
3. Implement blue/green deployments
4. Configure auto-scaling policies
5. Setup disaster recovery (cross-region backup)

### Cost Optimization
- Use Reserved Instances for predictable workloads (up to 60% savings)
- Enable auto-scaling to reduce off-peak costs
- Use Spot Instances for non-critical workloads
- Review and right-size instances monthly

---

## Support

For detailed deployment guides:
- **[docs/PHASE-6-AWS.md](docs/PHASE-6-AWS.md)** - Complete AWS deployment guide
- **[docs/DEPLOYMENT-CHECKLIST.md](docs/DEPLOYMENT-CHECKLIST.md)** - Production checklist
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture

For local development, see **[README.md](README.md)**.
