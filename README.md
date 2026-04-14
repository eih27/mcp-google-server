# Gmail & Calendar MCP Server

An MCP server exposing two read-only tools over Streamable HTTP:

- **`read_gmail`** — fetch recent Gmail messages, optionally filtered by sender
- **`read_calendar_events`** — fetch upcoming Google Calendar events

Designed for local development and MCP Inspector testing.

---

## Features

- Google OAuth 2.0 login flow (browser-based)
- In-memory session store (session_id returned after login, used as tool argument)
- Streamable HTTP transport compatible with MCP Inspector
- FastAPI serving auth routes and MCP on the same port
- No Docker, no database, no background processes

---

## Tech stack

- Python 3.11+
- FastAPI + Uvicorn
- MCP Python SDK (`mcp`)
- Google Auth + API Client libraries
- `uv` for package management

---

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed
- A Google Cloud project (setup below)
- [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector)

---

## Google Cloud setup

### 1. Create a project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown → **New Project**
3. Name it anything (e.g. `mcp-google-server`) → **Create**

### 2. Enable the APIs

In your project:

1. Go to **APIs & Services → Library**
2. Search for and enable:
   - **Gmail API**
   - **Google Calendar API**

### 3. Configure the OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External** → **Create**
3. Fill in:
   - App name: anything (e.g. `MCP Google Server`)
   - User support email: your email
   - Developer contact: your email
4. Click through the scopes screen (you don't need to add scopes here)
5. Under **Test users**, add your own Gmail address
6. Save and continue

### 4. Create OAuth credentials

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Application type: **Web application**
4. Name: anything
5. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:8000/auth/google/callback
   ```
6. Click **Create**
7. Copy the **Client ID** and **Client Secret**

---

## Local setup

```bash
# Clone or navigate to the project
cd mcp_google_server

# Install dependencies with uv
uv sync

# Copy env file and fill in your credentials
cp .env.example .env
```

Edit `.env`:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
HOST=0.0.0.0
PORT=8000
APP_BASE_URL=http://localhost:8000
```

---

## Run the server

```bash
uv run python main.py
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Verify it's up:

```bash
curl http://localhost:8000/health
# {"status":"ok","server":"gmail-calendar-mcp"}
```

---

## Authenticate

1. Open your browser and go to:
   ```
   http://localhost:8000/auth/google/login
   ```

2. You'll be redirected to Google's consent screen. Sign in with the Google account you added as a test user.

3. After approving, you'll be redirected back and see a page like:

   ```
   Authentication successful

   Your session ID:
   abc123xyz456...

   Use this as the session_id argument when calling tools in MCP Inspector.
   ```

4. **Copy the session ID** — you'll use it in every tool call.

---

## Connect MCP Inspector

1. Open MCP Inspector (run `npx @modelcontextprotocol/inspector` or use the web version)

2. Set connection:
   - **Transport type**: `Streamable HTTP`
   - **URL**: `http://localhost:8000/mcp`

3. Click **Connect**

4. Go to the **Tools** tab — you should see `read_gmail` and `read_calendar_events` listed.

---

## Example tool calls

### read_gmail

Minimal (last 5 messages):
```json
{
  "session_id": "your-session-id-here"
}
```

With filters:
```json
{
  "session_id": "your-session-id-here",
  "max_results": 10,
  "from_filter": "boss@company.com"
}
```

### read_calendar_events

Minimal (next 5 upcoming events):
```json
{
  "session_id": "your-session-id-here"
}
```

With time range:
```json
{
  "session_id": "your-session-id-here",
  "max_results": 10,
  "time_min": "2026-04-11T00:00:00Z",
  "time_max": "2026-04-18T00:00:00Z"
}
```

---

## Manual verification checklist

- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `GET /auth/google/login` redirects to Google
- [ ] After consent, callback page shows a session ID
- [ ] MCP Inspector connects to `http://localhost:8000/mcp` (Streamable HTTP)
- [ ] Tools tab in Inspector shows `read_gmail` and `read_calendar_events`
- [ ] `read_gmail` with valid `session_id` returns messages array
- [ ] `read_calendar_events` with valid `session_id` returns events array
- [ ] Both tools return `{"error": "Invalid or expired session_id."}` with a bad ID

---

## Troubleshooting

**`redirect_uri_mismatch` from Google**
→ The redirect URI in your `.env` must exactly match what you put in Google Cloud Console (including the `http://` and no trailing slash).

**`access_denied` on consent screen**
→ Your Google account must be added as a Test User under the OAuth consent screen settings.

**`OAUTHLIB_INSECURE_TRANSPORT` error**
→ This is handled automatically when the redirect URI starts with `http://`. If you see it anyway, set `export OAUTHLIB_INSECURE_TRANSPORT=1` in your shell before running.

**MCP Inspector says "connection refused"**
→ Make sure the server is running (`uv run python main.py`) and you're connecting to `[http://localhost:8000/sse](http://localhost:8000/mcp)` not `https://`.

**Session ID not working**
→ Sessions are in-memory. If the server restarted, your session ID is gone. Re-authenticate via `/auth/google/login`.

**`googleapiclient` file_cache warning in logs**
→ Harmless, suppressed by default in `google_clients.py`.

---

## Limitations

| Limitation | Detail |
|---|---|
| In-memory sessions | Sessions are lost on server restart. Not suitable for production. |
| Single-process only | Sharing sessions across multiple Uvicorn workers won't work without a shared store (Redis, etc.). |
| No HTTPS | OAuth over HTTP works locally via `OAUTHLIB_INSECURE_TRANSPORT`. Never use HTTP in production. |
| No token refresh | If the access token expires mid-session, tool calls will fail. Re-authenticate to fix. |
| Test user only | App is in "testing" mode in Google Cloud, so only whitelisted accounts can log in. |

---

## Possible production improvements

- Replace in-memory dict with Redis (token store with TTL + refresh)
- Add token refresh logic using `google.auth.transport.requests.Request`
- HTTPS with a real domain and proper OAuth redirect URI
- Publish OAuth app to move out of "testing" mode
- Add write tools (send email, create calendar event)
- Add per-session logging and audit trail
- Use Starlette sessions + secure cookies instead of explicit `session_id` in tool args

---

## Project structure

```
mcp_google_server/
├── main.py           FastAPI app + MCP Streamable HTTP transport wiring
├── config.py         Settings from env vars (pydantic-settings)
├── session_store.py  In-memory credential store
├── auth.py           Google OAuth 2.0 routes
├── google_clients.py Gmail + Calendar API service builders
├── tools.py          MCP Server instance + tool definitions
├── pyproject.toml    uv/hatchling project config
├── .env.example      Environment variable template
└── README.md
```
