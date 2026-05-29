# SENTASK Public Deployment (VPS + HTTPS)

## 1) Prepare DNS
- Point your domain `A` record to the VPS public IP.
- Example: `sentask.seneca.uz -> <VPS_IP>`.

## 2) Prepare VPS
- Ubuntu 22.04+ recommended.
- Install Docker + Compose plugin.
- Open ports `80` and `443` in firewall/security group.

## 3) Prepare environment file
- Copy `.env.public.example` to `.env.public`.
- Set at minimum:
  - `DOMAIN`
  - `ACME_EMAIL`
  - `APP_URL`
  - `NEXTAUTH_URL`
  - `NEXTAUTH_SECRET`
  - `CRON_SECRET`
  - `POSTGRES_PASSWORD`
- If using Google Workspace, also set Google OAuth and service-account variables.

## 4) Deploy from your local machine
```bash
cd "/path/to/SENTASK"
chmod +x scripts/deploy-public-vps.sh
SSH_TARGET=ubuntu@<VPS_IP> REMOTE_DIR=/opt/sentask ./scripts/deploy-public-vps.sh
```

## 5) Check status on VPS
```bash
cd /opt/sentask
docker compose -f docker-compose.public.yml --env-file .env.public ps
docker compose -f docker-compose.public.yml --env-file .env.public logs -f app
docker compose -f docker-compose.public.yml --env-file .env.public logs -f caddy
```

## 6) Google OAuth callback URL
- In Google Cloud OAuth credentials:
  - Authorized JavaScript origin: `https://<your-domain>`
  - Authorized redirect URI: `https://<your-domain>/api/auth/callback/google`

## 7) Update password-setup links for production
- Generate links with production base URL:
```bash
SETUP_LINK_BASE_URL="https://<your-domain>" \
node scripts/generate-password-setup-links.js <email1> <email2>
```
