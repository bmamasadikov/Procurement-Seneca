# SENTASK — Seneca Internal Task Manager
## Setup & Deployment Guide

---

## Quick Start (Development)

### Prerequisites
- Node.js 18+
- PostgreSQL 15+
- npm or yarn

### 1. Install dependencies
```bash
npm install --legacy-peer-deps
```

### 2. Configure environment
```bash
cp .env.example .env
```
Edit `.env` with your values:
```env
DATABASE_URL="postgresql://postgres:password@localhost:5432/sentask"
NEXTAUTH_URL="http://localhost:3000"
NEXTAUTH_SECRET="run: openssl rand -base64 32"
GOOGLE_CLIENT_ID="your-google-oauth-client-id"
GOOGLE_CLIENT_SECRET="your-google-oauth-client-secret"
GOOGLE_WORKSPACE_ALLOWED_DOMAINS="seneca.uz"
GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL="service-account@project.iam.gserviceaccount.com"
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
GOOGLE_WORKSPACE_DELEGATED_ADMIN_EMAIL="workspace-admin@seneca.uz"
GOOGLE_WORKSPACE_CALENDAR_IMPERSONATION_EMAIL="workspace-calendar-bot@seneca.uz"
GOOGLE_WORKSPACE_DEFAULT_CALENDAR_ID="c_9d7a3ee7e8637ae4e7026b1514ee9e13a127112dab4b464c2761fb81735b2546@group.calendar.google.com"
GOOGLE_WORKSPACE_DEFAULT_SENDER_EMAIL="noreply@seneca.uz"
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="your@email.com"
SMTP_PASS="your-app-password"
SMTP_FROM="SENTASK <noreply@seneca.uz>"
APP_URL="http://localhost:3000"
CRON_SECRET="long-random-secret"
```

Optional: Google Workspace integration
1. Open Google Cloud Console and create an OAuth 2.0 Client ID for a Web application
2. Add `http://localhost:3000` to Authorized JavaScript origins
3. Add `http://localhost:3000/api/auth/callback/google` to Authorized redirect URIs
4. Copy the generated client ID and secret into `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
5. Create a Google Cloud service account and enable Domain-Wide Delegation
6. In Google Workspace Admin, authorize the service account for Calendar, Gmail send, and Admin Directory scopes
7. Store the service account email and private key in env
8. Google sign-in is restricted to allowed Workspace domains, and new users can land in `PENDING` until an admin approves them

### 3. Create the database
```bash
createdb sentask
# or via psql:
psql -c "CREATE DATABASE sentask;"
```

If you do not have PostgreSQL running locally, start the repo-local container instead:
```bash
docker compose up -d
```
The bundled compose file uses the same default credentials as `.env`:
`postgresql://postgres:postgres@localhost:5432/sentask`

### 4. Push schema + seed
```bash
npm run db:push      # creates tables
npm run db:seed      # seeds demo data
```

### 5. Start dev server
```bash
npm run dev
# Open http://localhost:3000
```

---

## Demo Credentials (after seeding)

| Role    | Email             | Password    |
|---------|-------------------|-------------|
| Admin   | admin@seneca.uz   | admin123    |
| Manager | tulkin@seneca.uz  | manager123  |
| Manager | bekhroz@seneca.uz | manager123  |
| Staff   | sales@seneca.uz   | staff123    |
| Staff   | care@seneca.uz    | staff123    |

---

## Architecture Overview

```
SENTASK/
├── prisma/
│   ├── schema.prisma       # PostgreSQL schema
│   └── seed.ts             # Demo data seeder
├── src/
│   ├── app/
│   │   ├── (auth)/         # Public auth pages
│   │   │   ├── login/
│   │   │   └── forgot-password/
│   │   ├── (dashboard)/    # Protected app pages
│   │   │   ├── layout.tsx  # Sidebar + header wrapper
│   │   │   ├── dashboard/  # Overview + charts
│   │   │   ├── tasks/      # Task list, detail, edit, new
│   │   │   ├── my-tasks/   # Personal task view
│   │   │   ├── calendar/   # Monthly calendar
│   │   │   ├── reports/    # Analytics
│   │   │   ├── team/       # User management
│   │   │   └── settings/   # Templates + departments
│   │   └── api/            # REST API routes
│   │       ├── auth/       # NextAuth handler
│   │       ├── tasks/      # CRUD + comments
│   │       ├── users/      # User management
│   │       ├── notifications/
│   │       ├── departments/
│   │       ├── templates/
│   │       ├── reports/
│   │       └── forgot-password/
│   ├── components/
│   │   ├── layout/         # Sidebar, Header, NotificationBell
│   │   ├── tasks/          # TaskForm, TaskTable, TaskKanban, Filters
│   │   └── dashboard/      # StatsCard
│   ├── lib/
│   │   ├── prisma.ts       # Prisma client singleton
│   │   ├── auth.ts         # NextAuth v5 config
│   │   ├── email.ts        # Nodemailer email templates
│   │   └── utils.ts        # Helpers, constants
│   ├── types/index.ts      # Shared TypeScript types
│   └── middleware.ts       # Auth protection middleware
```

---

## Database Schema

Key tables:
- **users** — roles: ADMIN, MANAGER, STAFF
- **departments** — Sales, Operations, Customer Care, etc.
- **task_templates** — Reply Reviews, Update Extranet, Update Rate, Custom
- **tasks** — full task with status, priority, repeat, assignee, department
- **comments** — per-task discussion thread
- **attachments** — file uploads (stored as URLs)
- **notifications** — in-app notification center
- **audit_logs** — full activity trail
- **password_resets** — secure token-based reset

---

## Email Setup

### Google Workspace Gmail API (recommended for production)
- Preferred mode for SENTASK when using Seneca Google Workspace
- Uses a delegated service account plus Gmail API
- Supports Google-native sent mail, provider message IDs, and Workspace sender policies
- Configure `GOOGLE_WORKSPACE_DEFAULT_SENDER_EMAIL` and switch Gmail sending mode to `GMAIL_API` in Settings
- Keep SMTP configured as a fallback or for local development

### Gmail (recommended for testing)
1. Enable 2FA on your Google account
2. Create an App Password at myaccount.google.com/security
3. Use the 16-char app password as `SMTP_PASS`

### Production (Seneca mail server)
```env
SMTP_HOST="mail.seneca.uz"
SMTP_PORT="587"
SMTP_SECURE="false"
SMTP_USER="noreply@seneca.uz"
SMTP_PASS="your-mail-password"
```

---

## Production Deployment

### Option A: Vercel (recommended)
```bash
npm install -g vercel
vercel --prod
```
Set env vars in Vercel dashboard. Use Vercel Postgres or Neon for DB.
If Google sign-in is enabled, add your production callback URL too:
`https://your-domain.com/api/auth/callback/google`
Point your production domain to HTTPS before testing Google sign-in or Android install.

### Option B: VPS (Ubuntu/Nginx)
```bash
# Build
npm run build

# Start with PM2
npm install -g pm2
pm2 start npm --name "sentask" -- start
pm2 save && pm2 startup

# Nginx config
server {
  listen 80;
  server_name sentask.seneca.uz;
  location / {
    proxy_pass http://localhost:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
```

### Android install path
- The app now ships as a PWA, so once production is live over HTTPS you can open it in Chrome on Android and choose `Add to Home screen` or `Install app`.
- For Play Store distribution later, wrap the live site with Capacitor or Trusted Web Activity. This repo now includes the web manifest, service worker registration, and installable icons needed for that path.

---

## Security Notes
- Passwords hashed with bcrypt (cost factor 12)
- JWT sessions via NextAuth (no DB sessions)
- All API routes check session + role
- Only `tulkin@seneca.uz` and `bekhroz@seneca.uz` have full task visibility
- Everyone else can only access tasks they own or are assigned
- Admin-only: create users, manage departments, manage templates
- Input validated with Zod on all POST/PATCH endpoints
- Email enumeration prevention on password reset
- SQL injection prevention via Prisma parameterized queries
- XSS prevention via React JSX escaping

---

## Future Enhancements
- [ ] File upload (S3/Cloudflare R2)
- [ ] Telegram/WhatsApp notifications (Twilio / Telegram Bot API)
- [ ] Export reports to PDF/Excel
- [ ] Dark mode
- [ ] Play Store wrapper (Capacitor or Trusted Web Activity)
- [ ] Recurring task auto-generation cron job
- [ ] Webhook integrations
