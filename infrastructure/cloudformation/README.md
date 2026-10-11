# Staging CloudFormation Deployment

This directory provisions the staging foundation in `ap-southeast-2`.

## What is provisioned

- ECR repositories for API and four internal agent images.
- Two-AZ VPC with public load-balancer subnets and private ECS/RDS/Redis subnets.
- One NAT gateway for staging cost control.
- RDS PostgreSQL 16 instances for application and Nutrition Agent data.
- A single-node ElastiCache Redis instance. The application must implement Redis-backed sessions before API horizontal scaling is safe.
- ECS Fargate services for the API, Recovery Agent, Head Coach, Summarizer, and Nutrition Agent.
- API target tracking from two to three tasks at 60% CPU and 65% memory.
- An internet-facing staging ALB and an email-backed SNS topic when `AlertEmail` is supplied.

The workflow deploys a private S3 frontend bucket and CloudFront distribution after the API. CloudFront's generated `cloudfront.net` hostname supplies browser HTTPS without a custom domain. It serves the frontend at `/` and forwards uncached `/api/*` requests to the staging ALB.

## GitHub Environment configuration

Create a GitHub Environment named `staging`, then configure:

| Name | Type | Purpose |
| --- | --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | Variable | IAM role trusted by this repository through GitHub OIDC. |
| `ALERT_EMAIL` | Variable | Optional email recipient for SNS alarm notifications. |
| `APPLICATION_SECRET_ARN` | Secret | ARN of JSON secret containing `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `OPENAI_API_KEY`, `INTERNAL_SERVICE_TOKEN`, and optionally `USDA_FDC_API_KEY`. |
| `NUTRITION_SECRET_ARN` | Secret | ARN of JSON secret containing `NUTRITION_DATABASE_URL`. |

The deployment role needs CloudFormation, ECR, ECS, EC2/VPC, RDS, ElastiCache, IAM pass-role, CloudWatch Logs, Service Discovery, SNS, and Secrets Manager read/write permissions. It needs read access to the RDS-managed master secrets and write access only to the two runtime URL secrets during bootstrap. Restrict `iam:PassRole` to the execution and task roles created by this project.

## Bootstrap sequence

1. Create the GitHub OIDC provider and deployment role in the target AWS account.
2. Create placeholder Secrets Manager JSON secrets and add their ARNs to the GitHub `staging` Environment. Include all values in the examples below except database URLs; use an empty string for each database URL initially.
3. Trigger the workflow. It deploys ECR first, builds immutable images, creates the network/data stack without ECS services, populates database URLs using RDS-managed credentials, then deploys the ECS services.
4. Confirm the SNS subscription email, review the ALB health URL, and run the planned load tests.

Example application secret JSON:

```json
{
  "DATABASE_URL": "postgresql+asyncpg://main_app:<password>@<main-rds-endpoint>:5432/systemdb",
  "REDIS_URL": "redis://<redis-endpoint>:6379/0",
  "JWT_SECRET_KEY": "replace-with-a-long-random-value",
  "OPENAI_API_KEY": "replace-with-provider-key",
  "INTERNAL_SERVICE_TOKEN": "replace-with-a-long-random-value",
  "USDA_FDC_API_KEY": "optional-provider-key"
}
```

Example nutrition secret JSON:

```json
{
  "NUTRITION_DATABASE_URL": "postgresql://nutrition_agent:<password>@<nutrition-rds-endpoint>:5432/nutritiondb"
}
```

Do not store either JSON document in the repository or GitHub Actions configuration. Store the secret values in AWS Secrets Manager.

## Local validation

Run these commands in an environment with AWS CLI v2, `cfn-lint`, Docker, and Bash:

```bash
cfn-lint infrastructure/cloudformation/*.yaml
aws cloudformation validate-template --region ap-southeast-2 --template-body file://infrastructure/cloudformation/registry.yaml
aws cloudformation validate-template --region ap-southeast-2 --template-body file://infrastructure/cloudformation/staging.yaml
bash -n scripts/*.sh
```
