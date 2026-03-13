# Mann Made Socializer

A social media management platform for Mann Made Media. Schedule posts, manage client queues, run AI-assisted content generation, and track analytics across X, LinkedIn, Instagram, TikTok, YouTube, and Facebook.

## Features

- Multi-client management with per-client content queues
- AI content generation (via Claude Haiku)
- Post scheduling with calendar view
- Video upload and queuing
- Postiz integration for post delivery
- Google Sheets queue pipeline
- Role-based access control (admin / editor / viewer)
- Cloudflare Tunnel for external access

## Requirements

- Python 3.9+
- pip packages: `pip install -r requirements.txt`

## Setup

### 1. Configure secrets

Copy `secrets.json.example` to `secrets.json` and fill in your values:

```json
{
  "postiz": {
    "url": "http://your-postiz-instance:4007",
    "localUrl": "http://localhost:4007",
    "apiKey": "your-postiz-api-key"
  },
  "socializer": {
    "sheetId": "your-google-sheet-id",
    "jwtSecret": "generate-a-long-random-string"
  }
}
```

### 2. Set environment variables (optional)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export POSTIZ_URL=http://localhost:4007
export POSTIZ_API_KEY=your-key
```

### 3. Run the server

```bash
python3 server.py
```

The server starts on port 7070 by default. Open http://localhost:7070 in your browser.

### 4. Default login

On first run, an admin account is created. Check your deployment notes for the initial credentials, then change the password via user management.

## Roles

| Role   | Permissions |
|--------|-------------|
| admin  | Full access: add/remove clients, manage users, post, view all |
| editor | Manage content queues, schedule posts, view analytics |
| viewer | Read-only: dashboards, analytics, scheduled posts |

## User management

Log in as admin, go to the **Users** tab to add, remove, or change roles for users.

## Cloudflare Tunnel

To expose the socializer publicly via Cloudflare Tunnel:

```bash
# Install cloudflared
brew install cloudflare/cloudflare/cloudflared

# Start a quick tunnel (no account needed)
cloudflared tunnel --url http://localhost:7070
```

For a persistent tunnel with a custom domain, configure `~/.cloudflared/config.yml`.

## Client configuration

Each client has a JSON config in `clients/`. Use `clients/new-client-template.json` as a starting point. Client data files are excluded from version control to protect sensitive information.

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn server:app --reload --port 7070
```
