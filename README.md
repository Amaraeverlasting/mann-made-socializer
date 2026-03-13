# Mann Made Socializer

A social media management platform for Mann Made Media. Schedule posts, manage client queues, run AI-assisted content generation, and track analytics across X, LinkedIn, Instagram, TikTok, YouTube, and Facebook.

## Features

- Multi-client social media management
- Post scheduling and calendar view
- AI content generation (Claude Haiku)
- Video queue and upload pipeline
- Postiz integration for posting
- Google Sheets queue ingestion
- Analytics tracking
- Role-based access control (admin, editor, viewer)

## Auth System

Login is required for all pages. Users are stored in `data/users.json` (not committed to git).

### Roles

- **admin** - full access, can add/remove clients, manage users
- **editor** - manage content queues, schedule posts, view analytics
- **viewer** - read-only access to dashboards and analytics

### Default admin

`mic@mannmade.co.za` - password set on first run (stored in `data/users.json`)

## Setup

### Requirements

- Python 3.9+
- pip packages: see `requirements.txt`

```bash
pip install -r requirements.txt
```

### Environment

Copy `secrets.json.example` (if provided) to `secrets.json` and fill in:

```json
{
  "postiz": {
    "url": "http://localhost:4007",
    "apiKey": ""
  },
  "socializer": {
    "sheetId": "",
    "jwtSecret": "your-random-secret-here"
  }
}
```

Key environment variables (optional, override secrets.json):

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | For AI content generation |
| `POSTIZ_URL` | Postiz instance URL |
| `POSTIZ_API_KEY` | Postiz API key |

### Run

```bash
python3 server.py
# or
uvicorn server:app --host 0.0.0.0 --port 7070
```

Server starts at http://localhost:7070

### Using start.sh

```bash
chmod +x start.sh
./start.sh
```

## Client Config

Client configs live in `clients/`. See `clients/new-client-template.json` for the schema.

Each client can have:
- Multiple social accounts per platform
- A content inbox folder
- A Google Sheet queue
- A CDP port for browser automation

## Data Files (not in git)

- `data/users.json` - user accounts with hashed passwords
- `secrets.json` - API keys and JWT secret
- `clients/*.json` - client configs (excluded by .gitignore)

## License

Private - Mann Made Media
