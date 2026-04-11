"""
MCP tool definitions.

Tools:
  read_gmail            — fetch recent Gmail messages
  read_calendar_events  — fetch upcoming Calendar events

Both require a session_id obtained from /auth/google/login.
"""

import json
from datetime import datetime, timezone
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from google_clients import calendar_service, gmail_service
from session_store import get_credentials

# The MCP Server instance. main.py imports this and wires it to the SSE transport.
server = Server("gmail-calendar-mcp")


# ── Tool registry ──────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="read_gmail",
            description=(
                "Read recent Gmail messages for the authenticated user. "
                "Optionally filter by sender with from_filter."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID from /auth/google/login.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max messages to return (default 5).",
                        "default": 5,
                    },
                    "from_filter": {
                        "type": "string",
                        "description": "Filter by sender, e.g. boss@company.com.",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="read_calendar_events",
            description=(
                "Read upcoming Google Calendar events for the authenticated user. "
                "Defaults to events starting from right now."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID from /auth/google/login.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max events to return (default 5).",
                        "default": 5,
                    },
                    "time_min": {
                        "type": "string",
                        "description": "Start of time range (ISO 8601). Defaults to now.",
                    },
                    "time_max": {
                        "type": "string",
                        "description": "End of time range (ISO 8601). Optional.",
                    },
                },
                "required": ["session_id"],
            },
        ),
    ]


# ── Tool dispatcher ────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "read_gmail":
        result = await _read_gmail(arguments)
    elif name == "read_calendar_events":
        result = await _read_calendar_events(arguments)
    else:
        result = {"error": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


# ── Tool implementations ───────────────────────────────────────────────────────

async def _read_gmail(args: dict) -> dict:
    session_id = args.get("session_id", "")
    max_results = int(args.get("max_results", 5))
    from_filter = args.get("from_filter", "").strip()

    credentials = get_credentials(session_id)
    if not credentials:
        return {
            "error": "Invalid or expired session_id.",
            "fix": "Visit /auth/google/login to authenticate and get a new session_id.",
        }

    svc = gmail_service(credentials)
    query = f"from:{from_filter}" if from_filter else None

    try:
        list_resp = svc.users().messages().list(
            userId="me",
            maxResults=max_results,
            **({"q": query} if query else {}),
        ).execute()
    except Exception as e:
        return {"error": f"Gmail API error: {e}"}

    refs = list_resp.get("messages", [])
    if not refs:
        return {"messages": [], "count": 0}

    messages = []
    for ref in refs:
        try:
            msg = svc.users().messages().get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()

            hdrs = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            messages.append({
                "id": msg["id"],
                "thread_id": msg["threadId"],
                "subject": hdrs.get("Subject", "(no subject)"),
                "from": hdrs.get("From", ""),
                "date": hdrs.get("Date", ""),
                "snippet": msg.get("snippet", ""),
            })
        except Exception:
            continue  # skip individual message failures

    return {"messages": messages, "count": len(messages)}


async def _read_calendar_events(args: dict) -> dict:
    session_id = args.get("session_id", "")
    max_results = int(args.get("max_results", 5))
    time_min = args.get("time_min") or datetime.now(timezone.utc).isoformat()
    time_max = args.get("time_max")

    credentials = get_credentials(session_id)
    if not credentials:
        return {
            "error": "Invalid or expired session_id.",
            "fix": "Visit /auth/google/login to authenticate and get a new session_id.",
        }

    svc = calendar_service(credentials)

    params: dict[str, Any] = {
        "calendarId": "primary",
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
        "timeMin": time_min,
    }
    if time_max:
        params["timeMax"] = time_max

    try:
        resp = svc.events().list(**params).execute()
    except Exception as e:
        return {"error": f"Calendar API error: {e}"}

    items = resp.get("items", [])
    if not items:
        return {"events": [], "count": 0}

    events = []
    for ev in items:
        start = ev.get("start", {})
        end = ev.get("end", {})
        events.append({
            "id": ev["id"],
            "summary": ev.get("summary", "(no title)"),
            "start": start.get("dateTime") or start.get("date", ""),
            "end": end.get("dateTime") or end.get("date", ""),
            "location": ev.get("location", ""),
            "description": ev.get("description", ""),
            "status": ev.get("status", ""),
            "html_link": ev.get("htmlLink", ""),
        })

    return {"events": events, "count": len(events)}
