"""
Google OAuth 2.0 flow.

Routes:
  GET /auth/google/login    → redirects to Google consent screen
  GET /auth/google/callback → handles redirect, stores token, returns session_id
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

from config import settings
from session_store import create_session

router = APIRouter(prefix="/auth/google", tags=["auth"])

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# Temporary in-memory store for pending OAuth state values.
# Keyed by Google's `state` param → Flow object.
# NOTE: production would persist this in Redis with a short TTL.
_pending_flows: dict[str, Flow] = {}


def _build_flow() -> Flow:
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )


@router.get("/login")
async def login():
    """Start the Google OAuth flow. Visit this URL in your browser."""
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",          # force refresh token on every login
        include_granted_scopes="true",
    )
    _pending_flows[state] = flow
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(code: str, state: str):
    """Google redirects here after user grants permission."""
    flow = _pending_flows.pop(state, None)
    if not flow:
        return HTMLResponse(
            "<h1>Error</h1><p>Invalid or expired OAuth state. "
            "Please <a href='/auth/google/login'>try again</a>.</p>",
            status_code=400,
        )

    try:
        flow.fetch_token(code=code)
    except Exception as e:
        return HTMLResponse(
            f"<h1>Token exchange failed</h1><p>{e}</p>",
            status_code=400,
        )

    session_id = create_session(flow.credentials)

    return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
  <title>Authenticated</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 560px; margin: 60px auto; padding: 0 24px; }}
    code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
    pre  {{ background: #f4f4f4; padding: 16px; border-radius: 8px; font-size: 15px; word-break: break-all; }}
    .tip {{ color: #555; font-size: 14px; }}
  </style>
</head>
<body>
  <h2>Authentication successful</h2>
  <p>Your session ID:</p>
  <pre>{session_id}</pre>
  <p>Pass this as the <code>session_id</code> argument when calling tools in MCP Inspector.</p>
  <hr>
  <p class="tip">
    This session is stored in memory and will be lost if the server restarts.
    Re-visit <code>/auth/google/login</code> to get a new session ID.
  </p>
</body>
</html>
""")
