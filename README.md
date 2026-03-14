# Mann Made Socializer

A social media management platform for Mann Made Media. Schedule, manage, and post content across X, LinkedIn, Instagram, TikTok, YouTube, and Facebook.

## Features

- Multi-client social media management
- AI content generation via Larry (Claude + GPT-4o)
- Post scheduling with calendar view
- Approval workflow (admin/editor/viewer roles)
- Analytics and engagement tracking
- Video queue and clip generation
- Postiz integration for posting
- Google Sheets queue pipeline
- Hashtag set manager
- Brand DNA extractor

## Getting Started

### Requirements

- Python 3.10+
- pip packages: see `requirements.txt`

### Install dependencies

```bash
pip3 install -r requirements.txt
```

### Configure secrets

Create `secrets.json` in the project root:

```json
{
  "postiz": {
    "url": "http://localhost:5001",
    "apiKey": "your-postiz-api-key"
  },
  "socializer": {
    "sheetId": "your-google-sheet-id",
    "jwtSecret": "generate-a-random-secret-here"
  }
}
```

### Run the server

```bash
python3 server.py
```

Or use the start script:

```bash
./start.sh
```

The server runs on port 7070 by default: http://localhost:7070

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | For AI content generation (Larry) |
| `OPENAI_API_KEY` | For brand DNA extraction and batch generation |
| `GEMINI_API_KEY` | For AI image generation |
| `POSTIZ_API_KEY` | Postiz instance API key |
| `POSTIZ_URL` | Postiz instance URL (default: http://localhost:5001) |

## Auth and Roles

Three roles are supported:

- **admin** - full access, user management, client management
- **editor** - manage content queues, schedule posts, view analytics
- **viewer** - read-only access to dashboards and analytics

Users are stored in `data/users.json` (excluded from git). Create the default admin via the server startup or manually with bcrypt-hashed passwords.

## API Endpoints

### Auth
- `POST /api/auth/login` - login (public)
- `POST /api/auth/logout` - logout
- `GET /api/auth/me` - current user info
- `GET /api/auth/users` - list users (admin only)
- `POST /api/auth/users` - create user (admin only)
- `DELETE /api/auth/users/{email}` - remove user (admin only)
- `PUT /api/auth/users/{email}/role` - change role (admin only)

### Content
- `GET /api/posts` - list posts
- `POST /api/posts` - create post
- `GET /api/clients` - list clients
- `GET /api/analytics` - analytics data
- `POST /api/generate` - AI content generation
- `POST /api/larry/generate` - Larry AI generation

## Structure

```
mann-made-media/
  server.py          - FastAPI server
  auth.py            - JWT + bcrypt auth
  publisher.py       - Post publishing engine
  index.html         - Main dashboard
  login.html         - Login page
  clients.html       - Client management
  analytics.html     - Analytics view
  clients/           - Client configs (gitignored)
  data/              - Runtime data (mostly gitignored)
  scripts/           - Utility scripts
  videos/            - Video files
```

## Running with Cloudflare Tunnel

To expose the server externally:

```bash
cloudflared tunnel --url http://localhost:7070
```

For a persistent tunnel, configure `~/.cloudflared/config.yml` and use a LaunchAgent.

---

Built by Mann Made Media - South Africa
