# Deploy Multi-Agent Coach to one EC2 instance

Follow this guide for a low-cost school project or demonstration. GitHub Actions sends the source to one Ubuntu EC2 instance over SSH, builds the Docker Compose services there, and checks the API health endpoint. Expect a short outage during every deployment: the workflow stops running containers before rebuilding them. This is not a highly available production setup.

The finished application is available at `http://<EC2_PUBLIC_IP>:5174`; its API health check is at `http://<EC2_PUBLIC_IP>:8000/health`. Replace `<EC2_PUBLIC_IP>` in browser addresses with the actual public IP (do not type the angle brackets).

## Before you start

You need an AWS account, access to this repository's GitHub Actions settings, an OpenAI API key, and a local terminal with `ssh`, `ssh-keygen`, and `openssl`. Have an SSH key for initial EC2 access (the AWS launch wizard can create one). The commands below assume an Ubuntu 24.04 LTS instance with the default `ubuntu` user and `/opt/multi-agent-coach` as the application directory. Use your actual username everywhere if different. The workflow's Docker install uses Docker's **Ubuntu** apt repository, so choose Ubuntu for this walkthrough.

Check current AWS pricing and Free Tier eligibility before creating resources. A `t3.small` and a 20–30 GB gp3 root volume are a starting point; six application images plus two databases need disk space, and the deployment workflow requires at least **6 GiB free on the root filesystem after cleanup** before it builds. An Elastic IP is recommended for a stable address but may incur charges. Release unused resources when the project is finished.

The repository already includes the [EC2 Compose override](../docker-compose.ec2.yml) and [deployment workflow](../.github/workflows/deploy-ec2.yml). No additional deployment files need to be created for the first run.

## First deployment

### 1. Launch EC2 and record its address (AWS Console)

1. In **EC2 → Launch instance**, choose **Ubuntu Server 24.04 LTS** and start with `t3.small`. Set the root volume to **20–30 GB gp3**; use a larger volume if you expect many rebuilds or retained data.
2. Select or create an EC2 login key pair. Save its private key locally. Do not add this login key to the repository.
3. Create a security group with these **inbound TCP** rules:

   | Port | Source | Used for |
   | --- | --- | --- |
   | 22 | Your IP for setup; see note below for GitHub Actions | SSH deployment |
   | 5174 | Your IP or school network | Frontend |
   | 8000 | Your IP or school network | Browser API calls and external health check |

   Do not add inbound rules for database ports `5432`/`5433`, Redis `6379`, or agent ports `8001`–`8004`. The agent ports in the base Compose file bind to loopback on the host; the services also talk across the Compose network.
4. Launch the instance. Optionally allocate and associate an **Elastic IP**; record the address as `EC2_PUBLIC_IP`. Without an Elastic IP, update the GitHub settings in step 4 if the public IP changes after an instance restart.

GitHub-hosted runners have no fixed outbound IP. To let this workflow connect, port 22 must be reachable from the runner; the simplest setup is temporarily allowing `0.0.0.0/0` for SSH, with key authentication and password/root SSH login disabled. Restrict it again when deployments are finished, or use a runner with a known IP and allowlist that IP. Opening SSH to the internet increases exposure; keep the instance patched and protect the private key.

**Checkpoint:** you can see the instance running and have written down its public IP and the path to your EC2 login key.

### 2. Create a separate deployment SSH key (local computer)

The EC2 login key from step 1 lets you get in initially. Make a second key for GitHub Actions:

```bash
ssh-keygen -t ed25519 -C "github-actions-ec2-deploy" -f ~/.ssh/macoach-ec2-deploy
```

Press Enter for an empty passphrase: the current workflow cannot unlock a passphrase-protected key. Keep the private key local until you paste it into the GitHub secret in step 4. Use your login key to connect (replace the path and IP):

```bash
chmod 600 /path/to/ec2-login-key.pem
ssh -i /path/to/ec2-login-key.pem ubuntu@<EC2_PUBLIC_IP>
```

**Checkpoint:** the SSH prompt on EC2 shows the user you will enter as `EC2_USERNAME` (for example, `ubuntu`).

### 3. Prepare the deployment user (on EC2)

While logged in as that user, verify it can run non-interactive sudo. The workflow uses `sudo -n` to install missing dependencies and may create the application directory:

```bash
sudo -n true
```

If this fails, configure passwordless sudo for the deployment user using an administrator account before continuing. The default Ubuntu EC2 `ubuntu` user typically has it. The workflow installs Git, SSH, Docker Engine and Compose if missing; you do not need to install Docker manually.

Create the application directory and give the deployment user ownership:

```bash
sudo mkdir -p /opt/multi-agent-coach
sudo chown "$(id -un):$(id -gn)" /opt/multi-agent-coach
```

In a **second local terminal**, copy the public deployment key to EC2 (replace the login key path and IP):

```bash
ssh -i /path/to/ec2-login-key.pem ubuntu@<EC2_PUBLIC_IP> 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys' < ~/.ssh/macoach-ec2-deploy.pub
ssh -i ~/.ssh/macoach-ec2-deploy ubuntu@<EC2_PUBLIC_IP> 'whoami && sudo -n true && test -w /opt/multi-agent-coach'
```

**Checkpoint:** the second SSH command prints `ubuntu` (or your deployment username) and exits successfully. If it fails, fix SSH access or directory permissions before setting up GitHub.

### 4. Add GitHub Actions settings (GitHub repository)

Go to **Settings → Secrets and variables → Actions → Repository secrets**. Add the following names **exactly** as shown:

| Secret | What to enter |
| --- | --- |
| `EC2_HOST` | The EC2 public IP or reachable public hostname (without `http://`). |
| `EC2_USERNAME` | The SSH username tested in step 3, e.g. `ubuntu`. |
| `EC2_SSH_PRIVATE_KEY` | The entire contents of the local `~/.ssh/macoach-ec2-deploy` private key, including BEGIN/END lines; do **not** use `.pub`. |
| `EC2_PUBLIC_URL` | `http://<EC2_PUBLIC_IP>` with your real IP; no port or trailing slash. The workflow appends `:5174` and `:8000/api`. |
| `OPENAI_API_KEY` | Your OpenAI API key. |
| `JWT_SECRET_KEY` | A unique random JWT signing secret (at least 32 characters). |
| `INTERNAL_SERVICE_TOKEN` | A different random token shared by the API and agents. |
| `MAIN_DB_PASSWORD` | A unique strong password for the main PostgreSQL database. |
| `NUTRITION_DB_PASSWORD` | A different strong password for the nutrition PostgreSQL database. |
| `USDA_FDC_API_KEY` | Optional; set if you use USDA FoodData Central searches. |

For each random secret or password, run `openssl rand -hex 32` on your local computer and save its result directly as the corresponding GitHub secret. Use **four different values**. Never commit them or paste them into an issue or workflow log. For an existing database volume, keep its original password: changing a GitHub secret alone does not reset a PostgreSQL password stored in that volume.

Under **Actions → Variables → Repository variables**, you may set `EC2_APP_DIR` if you used a path other than `/opt/multi-agent-coach`; ensure the EC2 user owns that path. Otherwise, leave it unset. The automatic deployment branch is `main`, fixed in the workflow; there is no `DEPLOY_BRANCH` variable to set. **`EC2_PUBLIC_URL` is a secret, not a variable**, because the workflow reads it from `secrets`.

The workflow creates `/opt/multi-agent-coach/.env` from these settings, makes it readable only by the deployment user, and supplies the frontend and API URLs. You do not need to create `.env` on EC2. If the IP changes, update both `EC2_HOST` and `EC2_PUBLIC_URL` before redeploying: the frontend API URL is baked into its image at build time.

**Checkpoint:** every required secret above exists, the `EC2_PUBLIC_URL` starts with `http://`, and the tested SSH key's private half is in `EC2_SSH_PRIVATE_KEY`.

### 5. Run the first deployment (GitHub Actions)

Open **Actions → Deploy to EC2 → Run workflow**, choose `main`, leave the optional `ref` input as `main`, and start the run. The first build can take a while because the instance installs Docker if necessary and builds all six application images. Watch the workflow's **Deploy application to EC2** job. It checks out the selected revision on the GitHub runner, uploads a source archive to EC2, writes `.env`, validates Compose, builds the services, then polls `http://localhost:8000/health` on EC2 for up to about five minutes.

After that, a successful **CI** run on a push to `main` also triggers deployment automatically. A manual workflow run can deploy a specific commit, branch, or tag using its `ref` input; use a known-good commit for recovery. Manual runs do not wait for that ref's CI result, so prefer a commit that already passed CI.

**Checkpoint:** the deployment job is green and prints the Compose service status. If it fails, use the troubleshooting section below before retrying.

### 6. Verify from EC2 and your browser

On EC2, after the workflow succeeds:

```bash
cd /opt/multi-agent-coach
docker compose -f docker-compose.yml -f docker-compose.ec2.yml ps
curl --fail http://localhost:8000/health
```

On your own computer, open `http://<EC2_PUBLIC_IP>:5174` and check that the frontend can use the API. You can also visit `http://<EC2_PUBLIC_IP>:8000/health`. If local health works but the external URL does not, recheck ports `5174` and `8000` in the security group and your allowed source IP. The frontend uses HTTP here; do not send sensitive real user data over this demo setup.

## What the deployment runs

The base [docker-compose.yml](../docker-compose.yml) defines the API, frontend, four agents, two PostgreSQL databases and Redis. The EC2 override removes source-code bind mounts and hot reload, runs built images, and serves the frontend with Nginx. The workflow sets `SEED_DEMO_USERS=false`, `DEBUG=false`, and `RUN_MIGRATIONS=true`. It keeps database data in Compose named volumes on the instance.

Before building, the workflow stops existing containers and removes unused images and build cache, then checks for 6 GiB of free disk. It builds services one by one and starts them with `up -d --no-build --remove-orphans`. This process causes downtime, and a failed build leaves the app stopped until a successful deployment. The cleanup does not delete named volumes. **Do not run `docker compose down -v`** unless you intentionally want to remove database data after backing it up.

There is one EC2 point of failure, local database storage, no HTTPS by default, and no managed backups. S3 archival is not configured by this workflow. If reliability becomes important, plan backups and HTTPS before using this beyond a demonstration.

## Troubleshooting

Read the failed job step in **Actions → Deploy to EC2** first. Then, on EC2, inspect the deployment (use your custom directory if set):

```bash
cd /opt/multi-agent-coach
docker compose -f docker-compose.yml -f docker-compose.ec2.yml ps
docker compose -f docker-compose.yml -f docker-compose.ec2.yml logs --tail=200 api
docker compose -f docker-compose.yml -f docker-compose.ec2.yml logs --tail=200
```

- **SSH connection fails:** verify `EC2_HOST`, `EC2_USERNAME`, the deployment key, port 22's source rule, and that the instance is running. A new public IP requires updates to both host and public URL secrets.
- **Bootstrap says sudo needs a password:** run `sudo -n true` as the deployment user and configure passwordless sudo before retrying. If Docker group membership was just added, the workflow reconnects over SSH for deployment.
- **Application directory not writable:** log in as the user in `EC2_USERNAME` and run `sudo mkdir -p /opt/multi-agent-coach && sudo chown "$(id -un):$(id -gn)" /opt/multi-agent-coach` (substitute a custom `EC2_APP_DIR` if used). Retry the workflow.
- **Insufficient disk space:** inspect `df -h /` and `docker system df` on EC2. The workflow already prunes unused images and build cache; increase the EBS root volume if it still cannot keep 6 GiB free. Do not prune volumes to make space without a backup.
- **Frontend loads, API requests fail:** verify `EC2_PUBLIC_URL` contains the current IP, the frontend was rebuilt after any IP change, and port 8000 is reachable. The workflow sets `ALLOWED_ORIGINS` to the frontend URL and `VITE_API_BASE_URL` to the public API URL.
- **Services fail to start:** inspect the logs above. To validate the merged Compose file without printing resolved secrets in terminal output, run `docker compose -f docker-compose.yml -f docker-compose.ec2.yml config --quiet` from the application directory.

## Recover from a failed release

The workflow deploys an **archive**, so `/opt/multi-agent-coach` is not a Git checkout. There is no EC2 `git log` or `git checkout` rollback. Find a commit that passed CI in GitHub, then open **Actions → Deploy to EC2 → Run workflow**, enter that commit SHA in `ref`, and run it. Recheck the EC2 API health endpoint and frontend afterward. The same workflow rebuilds the images and keeps named database volumes; it does **not** undo database migrations or restore old data. Take a backup before changes that might alter data or schemas.

## Back up database data before major changes

From the application directory **on EC2**, while the databases are running:

```bash
cd /opt/multi-agent-coach
docker compose -f docker-compose.yml -f docker-compose.ec2.yml exec -T main-db pg_dump -U main_app -d systemdb > systemdb-backup.sql
docker compose -f docker-compose.yml -f docker-compose.ec2.yml exec -T nutrition-db pg_dump -U nutrition_agent -d nutritiondb > nutritiondb-backup.sql
```

Check that both files are nonempty, then move them to storage outside the instance if you need protection from instance loss. These dumps can contain sensitive data: restrict access and do not commit them. Named volumes survive a normal deployment, but a single EC2 instance is not a backup.