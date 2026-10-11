# Staging CloudFormation Deployment Guide

> **Staging v2 (current clean-stack path):** Deploy `infrastructure/cloudformation/staging-v2.yaml` to `macoach-staging-v2`. It is intentionally separate from the legacy `macoach-staging` stack and must not be used to replace it in place. V2 uses one private PostgreSQL instance with four isolated logical databases and roles: API, Recovery, Nutrition, and Training.

## Staging v2 deployment sequence

The v2 workflow uses pre-provisioned ECR repositories, builds digest-pinned
images (including `database-bootstrap`), and creates the v2 foundation with
`DeployServices=false`.
It then runs these private Fargate tasks in order:

1. `database-bootstrap` reads the RDS-managed master secret inside the VPC,
   creates or verifies the four databases/roles, revokes public database access,
   and writes TLS URLs to the four scoped runtime secrets.
2. API, Recovery, Nutrition, and Training migration tasks run sequentially.
3. Only after every one-off task succeeds does CloudFormation update the stack
   with `DeployServices=true`; the workflow waits and smoke-tests the ALB health
   endpoint.

Create these repository-level GitHub Actions secrets before deploying v2:

| Secret | Required JSON keys before bootstrap |
| --- | --- |
| `APPLICATION_SECRET_ARN` | `DATABASE_URL` (empty), `JWT_SECRET_KEY`, `OPENAI_API_KEY`, `INTERNAL_SERVICE_TOKEN` |
| `RECOVERY_SECRET_ARN` | `RECOVERY_DATABASE_URL` (empty) |
| `NUTRITION_SECRET_ARN` | `NUTRITION_DATABASE_URL` (empty) |
| `TRAINING_SECRET_ARN` | `TRAINING_DATABASE_URL` (empty) |
| `REDIS_AUTH_TOKEN_SECRET_ARN` | `password` |

Each GitHub Actions secret above must contain the complete ARN of an existing,
active AWS Secrets Manager secret in the deployment account and Singapore region,
for example `arn:aws:secretsmanager:ap-southeast-1:758248541054:secret:NAME-SUFFIX`.
Do not enter a secret name, console URL, secret JSON, partial ARN, or an ARN from
another account or region. Before CloudFormation creates the application change
set, the workflow validates each ARN and calls `DescribeSecret`; the deployment
role therefore requires `secretsmanager:DescribeSecret` for all five secrets.
The validation never reads or prints secret values. CloudFormation resolves the
Redis `password` dynamic reference while creating the replication group, so the
effective CloudFormation deployment identity also requires
`secretsmanager:GetSecretValue` for the Redis token secret only.

The GitHub deployment identity does **not** receive database master-secret or
runtime-secret update permissions. Those permissions belong exclusively to the
one-off bootstrap task role. Keep the legacy host-side
`scripts/bootstrap-runtime-secrets.sh` only for the legacy v1 stack; v2 never
uses it.

V2 includes one NAT gateway, single-AZ RDS, and a private, highly available
`cache.t4g.micro` Redis OSS replication group. Redis has one primary and one
replica in separate private Availability Zones, with Multi-AZ and automatic
failover enabled. It uses TLS in transit, encryption at rest, an externally
provisioned Secrets Manager AUTH token, and a security group that accepts
TCP/6379 only from ECS tasks. The template injects a `rediss://` `REDIS_URL` using the
primary endpoint only into API tasks, so sessions are shared when the API is
scaled, a task is replaced, or Redis fails over. At the estimated Singapore
on-demand rate of US$0.024 per node-hour, the two-node Redis topology costs about
US$8.06 for 168 hours (one week), excluding workload-dependent cross-AZ transfer
and all non-Redis resources. Delete the v2 CloudFormation stack and retained
RDS/Redis snapshots explicitly when the environment is no longer needed; review
snapshots, Secrets Manager secrets, ECR images, and CloudWatch logs before
teardown.

This guide explains how to deploy the application to the staging AWS environment through GitHub Actions and CloudFormation.

It implements the staging decisions recorded in [PRODUCTION-SCALE-CLOUDFORMATION-PLAN.md](PRODUCTION-SCALE-CLOUDFORMATION-PLAN.md):

- AWS Region: `ap-southeast-1` (Singapore).
- Database: separate RDS PostgreSQL 16 instances for application and Nutrition Agent data.
- Compute: ECS Fargate API service with minimum two and maximum three tasks.
- Public frontend: an ECS Nginx service behind the staging ALB, with same-origin `/api` routing.
- Transport: temporary HTTP-only ALB access while HTTPS/domain/ACM are deferred. Do not use real credentials or production data until HTTPS is enabled.
- Capacity objective: validate 100 concurrent patient sessions through load testing before making a capacity claim.

## Deployment Checklist

Complete this checklist before triggering the workflow.

| Item | Required action | Complete |
| --- | --- | --- |
| AWS account | Confirm the intended staging AWS account and access to administer initial IAM setup. | [ ] |
| AWS Region | Confirm staging deploys to `ap-southeast-1` (Singapore). | [ ] |
| ECR repositories | Confirm the eight pre-provisioned repositories listed below exist in the staging account. The workflow reuses them and does not create a registry CloudFormation stack. | [ ] |
| GitHub Actions configuration | Add repository-level variable `AWS_DEPLOY_ROLE_ARN` and repository-level secrets `APPLICATION_SECRET_ARN`, `RECOVERY_SECRET_ARN`, `NUTRITION_SECRET_ARN`, `TRAINING_SECRET_ARN`, and `REDIS_AUTH_TOKEN_SECRET_ARN`. | [ ] |
| OIDC provider | Create or confirm the AWS IAM OIDC provider for `token.actions.githubusercontent.com`. | [ ] |
| Deployment role | Create an AWS IAM role trusted by this repository's GitHub Actions workflow. | [ ] |
| OIDC restrictions | Restrict role assumption to this repository's `main` branch subject. | [ ] |
| GitHub variable | Add repository-level Actions variable `AWS_DEPLOY_ROLE_ARN`. | [ ] |
| Deployment controls | Protect `main` and restrict access to workflow files and Actions settings because Environment approval gates are not used. | [ ] |
| Runtime secrets | Create application, Recovery, Nutrition, and Training JSON secrets in `ap-southeast-1`. | [ ] |
| GitHub secrets | Add the five runtime-secret ARNs as repository-level Actions secrets. | [ ] |
| Secret permissions | Keep runtime and RDS master-secret access on scoped ECS roles; the GitHub deployment role does not read their values. | [ ] |
| LLM readiness | Confirm the configured LLM API key, spend controls, and staging quotas. | [ ] |
| Service quotas | Confirm the required quotas in `ap-southeast-1` (Singapore). | [ ] |
| Budget | Approve the staging budget, including NAT, RDS, ECS, ALB, and data transfer. | [ ] |
| Data | Use synthetic or otherwise approved staging data only. | [ ] |
| Session scaling | Run Redis session integration and multi-task continuity tests before claiming session safety or load capacity. | [ ] |

## 1. Review the Deployment Files

Confirm the following files are present on the branch to deploy:

This repository is self-contained: its deployment workflow responds only to this
repository's `CI` workflow, checks out this repository's tested commit, and
builds images from this repository's source. It does not trigger, check out, or
consume artifacts from another repository.

| File | Purpose |
| --- | --- |
| `.github/workflows/deploy-cloudformation.yml` | GitHub Actions deployment workflow. |
| `infrastructure/cloudformation/registry.yaml` | ECR repository template retained for reference; it is not deployed by the staging workflow because staging repositories are pre-existing. |
| `infrastructure/cloudformation/staging-v2.yaml` | VPC, RDS, scoped ECS execution roles, ECS, ALB, Cloud Map, IAM, and logging resources. |
| `scripts/build-and-push-images.sh` | Builds and publishes frontend and backend images to ECR. |
| `scripts/deploy-cloudformation.sh` | Creates, reviews, executes, and waits for CloudFormation change sets. |
| `scripts/validate-staging-secret-arns.sh` | Verifies the configured runtime-secret ARNs are active and belong to the deployment account and region. |
| `scripts/run-ecs-bootstrap.sh` | Runs the v2 private bootstrap task to populate isolated database URLs. |
| `scripts/run-ecs-migrations.sh` | Runs the ordered private ECS database migration tasks. |
| `scripts/smoke-test-staging.sh` | Checks the frontend and API endpoints through the ALB after ECS deployment. |

### Pre-provisioned ECR repositories

Before running the workflow, ensure these repositories exist in the deployment
account (`758248541054`) and `ap-southeast-1`:

- `macoach-staging/api`
- `macoach-staging/recovery-agent`
- `macoach-staging/head-coach`
- `macoach-staging/summarizer`
- `macoach-staging/nutrition-agent`
- `macoach-staging/training-agent`
- `macoach-staging/database-bootstrap`

The workflow builds and pushes directly to these names. Do not run a normal
CloudFormation create operation with `registry.yaml` while they exist, because
CloudFormation cannot create ECR repositories with names already owned outside
that stack.

## 2. Configure Repository-level GitHub Actions Values

The workflow deliberately does not select a GitHub Environment. In the repository,
open **Settings** > **Secrets and variables** > **Actions** and configure:

| Name | Kind | Value |
| --- | --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | Variable | ARN of the AWS GitHub OIDC deployment role. |
| `APPLICATION_SECRET_ARN` | Secret | ARN of the application Secrets Manager secret. |
| `RECOVERY_SECRET_ARN` | Secret | ARN of the Recovery Secrets Manager secret. |
| `NUTRITION_SECRET_ARN` | Secret | ARN of the Nutrition Secrets Manager secret. |
| `TRAINING_SECRET_ARN` | Secret | ARN of the Training Secrets Manager secret. |
| `REDIS_AUTH_TOKEN_SECRET_ARN` | Secret | ARN of the Redis AUTH token Secrets Manager secret. |

Repository-level configuration means GitHub Environment approval gates, wait
timers, and environment branch restrictions do not apply. Protect `main` with
branch rules and restrict who can modify deployment workflows and Actions settings.

## 3. Create or Confirm the AWS OIDC Provider

GitHub Actions authenticates to AWS through OpenID Connect. Do not create long-lived AWS access keys for GitHub.

1. Sign in to the target staging AWS account.
2. Open **IAM** > **Identity providers**.
3. Confirm an OIDC provider exists with:
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`
4. If it does not exist, create it with those values.

AWS documents this setup at <https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws>.

## 4. Create the GitHub Deployment Role

Create a role such as `macoach-staging-github-deploy-role`.

### Trust policy

Restrict the role to this GitHub repository's `main` branch. Replace
`YOUR_ORGANISATION` and `YOUR_REPOSITORY`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORGANISATION/YOUR_REPOSITORY:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### Permissions

For initial setup, grant a reviewed deployment policy that permits the workflow to manage only the resources declared by the staging templates:

- CloudFormation stack/change-set operations.
- ECR repository/image operations.
- ECS cluster, task-definition, service, and service-autoscaling operations.
- EC2 VPC, subnet, route table, NAT gateway, Elastic IP, security group, and load-balancer related operations.
- RDS database creation/inspection.
- Cloud Map service discovery.
- CloudWatch Logs, CloudWatch alarms, and SNS topic/subscription operations.
- S3 and CloudFront operations for frontend publishing.
- `secretsmanager:DescribeSecret` on the five supplied runtime and Redis token
  secrets, so the preflight can confirm their active complete ARNs without
  reading values.
- `secretsmanager:GetSecretValue` on the Redis token secret, so CloudFormation
  can resolve its dynamic reference for ElastiCache. If it uses a customer-managed
  KMS key, grant the effective CloudFormation deployment identity `kms:Decrypt`
  for that key as well.
- No read access to runtime-secret values or the RDS-managed master secret; the
  bootstrap ECS task role receives that access instead.
- `iam:PassRole` restricted to the ECS task execution and task roles created by this deployment.

The `Deployer` role requires the following CloudWatch Logs permissions to create
the v2 `/ecs/macoach/staging/v2` log group and set its 30-day retention policy:

```json
{
  "Sid": "ManageMacoachStagingLogGroups",
  "Effect": "Allow",
  "Action": [
    "logs:CreateLogGroup",
    "logs:PutRetentionPolicy",
    "logs:DeleteLogGroup"
  ],
  "Resource": "arn:aws:logs:ap-southeast-1:758248541054:log-group:/ecs/macoach/staging/*"
}
```

Do not grant unrestricted administrative access for ongoing deployment. Have the policy reviewed before using real patient data.

## 5. Create Runtime Secrets in AWS Secrets Manager

Create five JSON secrets in `ap-southeast-1` (Singapore). Use secret names such as:

- `macoach/staging/application`
- `macoach/staging/recovery`
- `macoach/staging/nutrition`
- `macoach/staging/training`
- `macoach/staging/redis-auth-token`

The database URL fields begin empty because the RDS endpoints and generated master credentials do not exist until the first deployment run.

### Application secret

```json
{
  "DATABASE_URL": "",
  "JWT_SECRET_KEY": "replace-with-a-long-random-value",
  "OPENAI_API_KEY": "replace-with-the-staging-provider-key",
  "INTERNAL_SERVICE_TOKEN": "replace-with-a-long-random-value",
  "USDA_FDC_API_KEY": "optional-food-data-key"
}
```

### Service secrets

```json
{
  "RECOVERY_DATABASE_URL": ""
}
```

```json
{
  "NUTRITION_DATABASE_URL": ""
}
```

```json
{
  "TRAINING_DATABASE_URL": ""
}
```

### Redis AUTH token secret

```json
{
  "password": "replace-with-a-random-redis-auth-token"
}
```

The `password` value must be 16–128 printable characters. If it contains
non-alphanumeric characters, ElastiCache permits only `!`, `&`, `#`, `$`, `^`,
`<`, `>`, and `-`. Generate and store this value directly in Secrets Manager;
do not add it to GitHub or the repository. The secret must exist and have an
`AWSCURRENT` version before the CloudFormation change set is created.

Record all five ARNs. Add only the ARN of this Redis secret to the repository
Actions secret `REDIS_AUTH_TOKEN_SECRET_ARN`; never add its JSON value.

## 6. Confirm Repository Actions Values

Confirm the repository-level Actions variable and secrets listed in
[Configure Repository-level GitHub Actions Values](#2-configure-repository-level-github-actions-values)
are present. No `ALERT_EMAIL` value is used by the v2 template.

Example role ARN:

```text
arn:aws:iam::123456789012:role/macoach-staging-github-deploy-role
```

## 7. Confirm AWS Service Quotas and Budget

In the AWS `ap-southeast-1` (Singapore) region, confirm the account can create:

- One VPC, four subnets, an internet gateway, one NAT gateway, and one Elastic IP.
- One Application Load Balancer.
- Six ECS Fargate services and their tasks.
- One RDS PostgreSQL 16 instance.
- Five ECR repositories.
- One CloudFront distribution and one S3 bucket.

Review the expected staging cost before deployment. The NAT gateway and RDS instance are likely to be the most significant always-on charges.

## 8. Trigger the Deployment

You can deploy manually or automatically after CI succeeds for a push to `main`.

### Manual deployment

1. Open the GitHub repository's **Actions** tab.
2. Select **Deploy staging with CloudFormation**.
3. Select **Run workflow**.
4. Choose the branch containing the deployment files, normally `main`.
5. Select **Run workflow**.
6. Open the run and monitor each step.

### Automatic deployment

Every push or merge to `main` starts the `CI` workflow. CloudFormation deployment
starts only after every CI job succeeds; a failed or cancelled CI run skips the
deployment. The deployment workflow checks out the exact commit SHA validated by
CI before building images and applying the stack. This gate is local to this
repository; it does not wait for, invoke, or use artifacts from another
repository.

The DeepEval and Promptfoo workflows remain post-merge/manual evaluations because
they use the paid `OPENAI_API_KEY` secret. They are not part of the automatic
CloudFormation deployment gate.

## 9. What the First Workflow Run Does

The initial workflow follows this sequence:

1. Assumes the AWS deployment role through GitHub OIDC.
2. Reuses an existing immutable image tag or builds and pushes the frontend, API, Recovery Agent, Head Coach, Summarizer, Nutrition Agent, Training Agent, and database-bootstrap images to the pre-provisioned ECR repositories using the commit SHA as the image tag. The frontend is built with `VITE_API_BASE_URL=/api`.
3. Creates the staging CloudFormation stack with `DeployServices=false`.
4. Creates networking, RDS, scoped ECS task definitions, ALB, service discovery, and logging resources without starting ECS services.
5. Runs the private bootstrap task, which reads the RDS-managed master secret and creates or verifies isolated databases and roles.
6. Writes the generated database URLs into the four scoped runtime Secrets Manager secrets.
7. Updates the staging stack with `DeployServices=true`.
8. Starts the frontend, API, and internal agent ECS services.
9. Waits for both the frontend and API health endpoint to respond through the ALB.

Later workflow runs retain the ECS services while updating infrastructure and container images.

### ALB routes and temporary transport

The application stack (`macoach-staging-v2`) and frontend service are both in
Singapore (`ap-southeast-1`). Its public ALB routes `/api` and `/api/*` to the
API service on port 8000, and sends all other paths to the Nginx frontend
service on port 5174. This preserves the `/api` prefix, so browser API calls
are same-origin and do not need frontend-to-API networking or CORS changes.

`FrontendUrl` is currently an `http://` ALB URL. This temporary staging route
is not suitable for credentials or production traffic. Add a domain, ACM
certificate, HTTPS listener, and HTTP-to-HTTPS redirect before using it beyond
synthetic staging validation. After the ALB route is validated, manually retire
the failed CloudFront frontend stack.

## 10. Verify the Deployment

### GitHub Actions checks

Confirm these steps succeeded:

- `Build and push service images`
- `Deploy staging stack` on the first run only
- `Bootstrap isolated runtime databases and secrets`
- `Run ordered ECS migrations`
- `Deploy ECS services`
- `Smoke test frontend and API`

### AWS checks

1. Open **CloudFormation** and confirm `macoach-staging-v2` completes successfully in `ap-southeast-1`.
2. Copy its `FrontendUrl` output, which will resemble:

```text
http://macoach-staging-v2-123456.ap-southeast-1.elb.amazonaws.com
```

3. Open the URL in a browser and confirm frontend assets load.
4. Confirm `http://<ALB-DNS>/api/health` succeeds and test an API request with synthetic data only.
5. Check ECS service events and CloudWatch logs if either target group fails its health check.
6. Confirm the Redis replication group has one primary, TLS enabled, and no public access.

## 11. Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| OIDC authentication fails | Deployment role trust policy does not match the repository `main` branch, or role ARN is wrong. | Check repository variable `AWS_DEPLOY_ROLE_ARN` and the `repo:OWNER/REPOSITORY:ref:refs/heads/main` `sub` condition. |
| ECR push fails | A required repository is absent or the deployment role lacks ECR permissions. | Confirm all eight pre-provisioned repositories exist and check ECR permissions. Existing immutable commit-SHA tags are reused safely on a workflow retry. |
| Stack creation fails before ECS starts | Invalid secret ARN, insufficient AWS permissions, unsupported quota, or resource naming collision. | Review the workflow's secret-ARN preflight first. If change-set creation fails, inspect its printed change-set status/reason; no stack events exist until a stack is created. |
| ECS tasks fail to start | Runtime secret JSON is missing a required key, the scoped execution role cannot read its injected secret, or image startup fails. | Check ECS stopped-task reason and CloudWatch Logs. |
| API health check fails | Database or Redis URL is invalid, migrations fail, API image fails to start, or security groups block database/Redis access. | Check API logs, RDS endpoint/secret values, Redis primary endpoint, and security group rules. |
| Frontend loads but API calls fail | The frontend image was not built with `/api`, the API listener rule is absent, or an ALB target is unhealthy. | Confirm the image build uses `VITE_API_BASE_URL=/api`, inspect the `/api` and `/api/*` listener rule, and inspect browser network requests. |
| Browser warns that the site is insecure | The temporary ALB listener is HTTP-only. | Use synthetic data only; add a domain, ACM certificate, HTTPS listener, and redirect before handling credentials. |
| Workflow runs but does not update expected infrastructure | The GitHub path filter did not match the changed files. | Use **Run workflow** manually or update the workflow path filters. |

## 12. Redis-backed API Scaling and Load Testing

V2 starts two API tasks by default through the `ApiDesiredCount` template
parameter. Each receives the same TLS `REDIS_URL`, while bootstrap, migration,
and internal service tasks do not receive Redis configuration. This makes it safe
to exercise shared active sessions through the ALB during staging tests.

Before relying on this for patient traffic:

1. Run `tests/test_redis_session_manager.py` against a disposable TLS-capable
   Redis endpoint by setting `TEST_REDIS_URL`.
2. Validate a session can continue after requests reach different API tasks and
   after one API task is replaced.
3. Run baseline load tests at 10 and 100 concurrent patient sessions.
4. Review Redis CPU, memory, connections, evictions, and replication-group events
   alongside RDS, ECS, ALB, agent, and LLM-provider metrics.
5. Trigger and observe a controlled Redis failover, then verify session
   continuity through the primary endpoint after DNS reconnection. Review
   replication-group events and ensure the replica is restored in the other
   Availability Zone.
6. Adjust `ApiDesiredCount` for a controlled test. This topology has one primary
   and one replica with automatic failover; it is highly available for a single
   Redis OSS shard, not a multi-region or multi-shard design.

Do not claim support for 100 concurrent patient sessions until those tests succeed.
