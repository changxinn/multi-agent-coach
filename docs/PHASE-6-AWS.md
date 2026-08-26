# Phase 6: AWS Deployment Guide

**Status**: ⏳ Pending  
**Goal**: Deploy Multi-Agent Coach to AWS production environment

---

## Overview

This guide covers deploying the FastAPI backend to AWS using ECS Fargate, RDS PostgreSQL, ElastiCache Redis, and S3 for chat history archival.

---

## Architecture

```
┌─────────────────┐
│  Application    │
│  Load Balancer  │
│     (ALB)       │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│ ECS   │ │ ECS   │
│ Task 1│ │ Task 2│
│(Fargate)│(Fargate)
└───┬───┘ └──┬────┘
    │        │
    └───┬────┘
        │
   ┌────┴────┬──────────┬──────────┐
   │         │          │          │
┌──▼──┐ ┌───▼────┐ ┌───▼────┐ ┌──▼──────┐
│ RDS │ │Elasti  │ │   S3   │ │Secrets  │
│PostgreSQL│ │Cache   │ │ Bucket │ │ Manager │
│       │ │ Redis │ │        │ │         │
└──────┘ └────────┘ └────────┘ └─────────┘
```

---

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Docker installed locally
- Terraform (optional, for infrastructure as code)
- Completed Phases 1-5

---

## Step 1: Create S3 Bucket for Chat History

```bash
# Create bucket
aws s3api create-bucket \
  --bucket multi-agent-coach-chat-history \
  --region us-east-1 \
  --create-bucket-configuration LocationConstraint=us-east-1

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

---

## Step 2: Setup RDS PostgreSQL

```bash
# Create DB subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name multi-agent-coach-subnet \
  --db-subnet-group-description "Subnet group for Multi-Agent Coach" \
  --subnet-ids subnet-xxxxx subnet-yyyyy

# Create security group for RDS
aws ec2 create-security-group \
  --group-name multi-agent-coach-rds-sg \
  --description "Security group for RDS"

# Create RDS instance
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
  --vpc-security-group-ids sg-xxxxx \
  --multi-az \
  --backup-retention-period 7 \
  --tags Key=Project,Value=MultiAgentCoach
```

**RDS Configuration:**
- Engine: PostgreSQL 16.2
- Instance: db.t3.medium (scale as needed)
- Storage: 100 GB GP3
- Multi-AZ: Enabled for production
- Backup retention: 7 days
- Auto minor version upgrade: Enabled

---

## Step 3: Setup ElastiCache Redis

```bash
# Create Redis subnet group
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name multi-agent-coach-redis \
  --cache-subnet-group-description "Redis subnet group" \
  --subnet-ids subnet-xxxxx subnet-yyyyy

# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id multi-agent-coach-redis \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.t3.medium \
  --num-cache-nodes 2 \
  --cache-subnet-group-name multi-agent-coach-redis \
  --security-group-ids sg-xxxxx \
  --snapshot-retention-limit 7
```

**Redis Configuration:**
- Engine: Redis 7.0
- Node type: cache.t3.medium
- Nodes: 2 (for high availability)
- Snapshot retention: 7 days

---

## Step 4: Create ECR Repository

```bash
# Create repository
aws ecr create-repository \
  --repository-name multi-agent-coach-api \
  --image-scanning-configuration scanOnPush=true \
  --image-tag-mutability IMMUTABLE

# Get login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

---

## Step 5: Build and Push Docker Image

```bash
# Build Docker image
docker build -t multi-agent-coach-api:latest .

# Tag for ECR
docker tag multi-agent-coach-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/multi-agent-coach-api:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/multi-agent-coach-api:latest
```

---

## Step 6: Store Secrets in AWS Secrets Manager

```bash
# Create secret
aws secretsmanager create-secret \
  --name multi-agent-coach/prod \
  --secret-string '{
    "DATABASE_URL": "postgresql+asyncpg://postgres:PASSWORD@multi-agent-coach-db.xxxx.us-east-1.rds.amazonaws.com:5432/systemdb",
    "JWT_SECRET_KEY": "your-super-secret-key-min-32-chars",
    "OPENAI_API_KEY": "sk-proj-...",
    "REDIS_URL": "redis://multi-agent-coach-redis.xxxx.ng.0001.use1.cache.amazonaws.com:6379",
    "AWS_REGION": "us-east-1",
    "S3_BUCKET": "multi-agent-coach-chat-history"
  }'
```

---

## Step 7: Create ECS Task Definition

```bash
# Create task definition JSON
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
        {
          "name": "APP_NAME",
          "value": "Multi-Agent Coach API"
        },
        {
          "name": "DEBUG",
          "value": "false"
        }
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
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:multi-agent-coach/prod:secret-id::REDIS_URL"
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

---

## Step 8: Create ECS Service

```bash
# Create cluster
aws ecs create-cluster \
  --cluster-name multi-agent-coach-cluster

# Create service
aws ecs create-service \
  --cluster multi-agent-coach-cluster \
  --service-name multi-agent-coach-service \
  --task-definition multi-agent-coach-api \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-xxxxx", "subnet-yyyyy"],
      "securityGroups": ["sg-xxxxx"],
      "assignPublicIp": "ENABLED"
    }
  }' \
  --load-balancers '{
    "targetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:<account-id>:targetgroup/multi-agent-coach-tg/xxxxx",
    "containerName": "api",
    "containerPort": 8000
  }'
```

---

## Step 9: Configure Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name multi-agent-coach-alb \
  --subnets subnet-xxxxx subnet-yyyyy \
  --security-groups sg-xxxxx \
  --scheme internet-facing

# Create target group
aws elbv2 create-target-group \
  --name multi-agent-coach-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxxxx \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:<account-id>:loadbalancer/app/multi-agent-coach-alb/xxxxx \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:<account-id>:targetgroup/multi-agent-coach-tg/xxxxx
```

**For HTTPS (Production):**
- Request SSL certificate via AWS Certificate Manager
- Create HTTPS listener on port 443
- Redirect HTTP to HTTPS

---

## Step 10: Update Environment Configuration

**Production `.env` (stored in Secrets Manager):**

```env
# Application
APP_NAME=Multi-Agent Coach API
APP_VERSION=1.0.0
DEBUG=false

# Database (RDS)
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@multi-agent-coach-db.xxxx.us-east-1.rds.amazonaws.com:5432/systemdb
DATABASE_SCHEMA=systemdb

# JWT
JWT_SECRET_KEY=your-super-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# Session
SESSION_EXPIRY_HOURS=24
REDIS_URL=redis://multi-agent-coach-redis.xxxx.ng.0001.use1.cache.amazonaws.com:6379

# LLM
OPENAI_API_KEY=sk-proj-...
LLM_MODEL=gpt-5-nano

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<from-IAM-role>
AWS_SECRET_ACCESS_KEY=<from-IAM-role>
S3_BUCKET=multi-agent-coach-chat-history
S3_PREFIX=chat-history

# CORS
FRONTEND_URL=https://your-production-domain.com
ALLOWED_ORIGINS=https://your-production-domain.com
```

---

## Terraform Alternative (Recommended)

For infrastructure as code, use Terraform:

```hcl
# main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# RDS PostgreSQL
resource "aws_db_instance" "main" {
  identifier           = "multi-agent-coach-db"
  engine              = "postgres"
  engine_version      = "16.2"
  instance_class      = "db.t3.medium"
  allocated_storage   = 100
  storage_type        = "gp3"
  master_username     = "postgres"
  master_password     = var.db_password
  multi_az            = true
  backup_retention_period = 7
  skip_final_snapshot = true
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "multi-agent-coach-redis"
  engine              = "redis"
  engine_version      = "7.0"
  node_type           = "cache.t3.medium"
  num_cache_nodes     = 2
  parameter_group_name = "default.redis7"
  port                = 6379
}

# S3 Bucket
resource "aws_s3_bucket" "chat_history" {
  bucket = "multi-agent-coach-chat-history"
}

# ECR Repository
resource "aws_ecr_repository" "api" {
  name                 = "multi-agent-coach-api"
  image_tag_mutability = "IMMUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "multi-agent-coach-cluster"
}

# ECS Task Definition
resource "aws_ecs_task_definition" "api" {
  family                   = "multi-agent-coach-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "api"
    image = aws_ecr_repository.api.repository_url
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "APP_NAME", value = "Multi-Agent Coach API" },
      { name = "DEBUG", value = "false" }
    ]
    secrets = [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret_version.main.arn }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/multi-agent-coach-api"
        "awslogs-region"        = "us-east-1"
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] All local tests passing
- [ ] Docker image builds successfully
- [ ] Environment variables documented
- [ ] Database migrations tested
- [ ] Security scan completed (ECR scanning)

### Infrastructure
- [ ] VPC and subnets configured
- [ ] Security groups configured
- [ ] RDS PostgreSQL created
- [ ] ElastiCache Redis created
- [ ] S3 bucket created with encryption
- [ ] ECR repository created
- [ ] Secrets Manager configured
- [ ] IAM roles and policies created

### Deployment
- [ ] Docker image pushed to ECR
- [ ] Task definition registered
- [ ] ECS service created
- [ ] Load balancer configured
- [ ] Health checks passing
- [ ] CloudWatch logs enabled
- [ ] Auto-scaling configured

### Post-Deployment
- [ ] Smoke tests passing
- [ ] Database migrations run
- [ ] Admin user created
- [ ] Monitoring dashboards created
- [ ] Alerts configured
- [ ] Documentation updated

---

## Monitoring & Alerts

### CloudWatch Alarms

```bash
# CPU utilization
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

# Memory utilization
aws cloudwatch put-metric-alarm \
  --alarm-name "MultiAgentCoach-HighMemory" \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --dimensions Name=ClusterName,Value=multi-agent-coach-cluster Name=ServiceName,Value=multi-agent-coach-service \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:<account-id>:alerts

# RDS connections
aws cloudwatch put-metric-alarm \
  --alarm-name "MultiAgentCoach-RDSConnections" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value=multi-agent-coach-db \
  --statistic Average \
  --period 300 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:<account-id>:alerts
```

---

## Cost Optimization

### Estimated Monthly Costs (us-east-1)

| Service | Configuration | Estimated Cost |
|---------|--------------|----------------|
| ECS Fargate | 2 tasks, 1 vCPU, 2GB | ~$60 |
| RDS PostgreSQL | db.t3.medium, 100GB | ~$100 |
| ElastiCache Redis | 2 nodes, cache.t3.medium | ~$50 |
| S3 | 10GB storage | ~$1 |
| ALB | 1 load balancer | ~$20 |
| **Total** | | **~$231/month** |

### Cost Saving Tips

1. **Use Spot Instances** for non-critical workloads (30-70% savings)
2. **Right-size instances** based on actual usage
3. **Enable auto-scaling** to scale down during low traffic
4. **Use Reserved Instances** for predictable workloads (up to 60% savings)
5. **Clean up unused resources** (old Docker images, snapshots)

---

## Security Best Practices

1. **Network Security**
   - Use private subnets for RDS and ElastiCache
   - Security groups with minimal required access
   - VPC flow logs for network monitoring

2. **Data Security**
   - Encrypt RDS at rest and in transit
   - Enable Redis AUTH
   - S3 bucket encryption (SSE-S3 or SSE-KMS)
   - SSL/TLS for all communications

3. **Access Control**
   - IAM roles for ECS tasks (no hardcoded credentials)
   - Secrets Manager for sensitive data
   - Least privilege principle

4. **Monitoring**
   - CloudWatch Logs for application logs
   - CloudWatch Metrics for performance
   - AWS CloudTrail for API auditing
   - GuardDuty for threat detection

---

## Troubleshooting

### Issue: ECS Task Won't Start

**Check:**
```bash
aws ecs describe-tasks \
  --cluster multi-agent-coach-cluster \
  --tasks <task-arn>
```

**Common causes:**
- IAM role permissions missing
- VPC/subnet configuration issues
- Resource limits exceeded

### Issue: Database Connection Failed

**Check:**
- Security group allows ECS task security group
- RDS is in same VPC or has VPC peering
- Database URL is correct in Secrets Manager

### Issue: High Latency

**Check:**
- ECS task and RDS in same region
- Use ElastiCache for session storage
- Enable RDS Performance Insights
- Check CloudWatch metrics

---

## Next Steps

After successful deployment:

1. **Setup CI/CD Pipeline**
   - GitHub Actions or AWS CodePipeline
   - Automated testing
   - Blue/green deployments

2. **Implement Disaster Recovery**
   - Cross-region RDS read replica
   - Automated backups
   - Recovery time objective (RTO) < 1 hour

3. **Performance Optimization**
   - Enable RDS read replicas
   - Implement caching strategies
   - Use CloudFront for static assets

---

**Status**: Template ready for implementation  
**Last Updated**: 2026-08-24  
**Dependencies**: All previous phases complete  
**Estimated Setup Time**: 2-4 hours
