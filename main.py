"""
main.py — FastAPI app + MCP server wired together.

Architecture:
  - FastAPI handles /health, /auth/google/*
  - MCP Streamable HTTP transport is mounted at /mcp
  - StreamableHTTPSessionManager runs inside FastAPI's lifespan context
  - Both share the same process and port

MCP Inspector connection:
  Transport type: Streamable HTTP
  URL: http://localhost:8000/mcp
"""

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from auth import router as auth_router
from config import settings
from tools import server as mcp_server

# Allow OAuth over plain HTTP during local development.
# In production, this env var must NOT be set and HTTPS is required.
if settings.google_redirect_uri.startswith("http://"):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# StreamableHTTPSessionManager manages per-session transports and clean shutdown.
# stateless=False (default) means sessions are tracked server-side by session ID.
session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    event_store=None,   # no event replay needed for this demo
    json_response=False,
    stateless=False,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the MCP session manager on startup, shut it down on exit."""
    async with session_manager.run():
        yield


app = FastAPI(title="Gmail & Calendar MCP Server", lifespan=lifespan)

# ── HTTP routes ────────────────────────────────────────────────────────────────

app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok", "server": "gmail-calendar-mcp"}


@app.get("/")
async def root():
    return JSONResponse({
        "message": "Gmail & Calendar MCP Server",
        "auth": f"{settings.app_base_url}/auth/google/login",
        "mcp_url": f"{settings.app_base_url}/mcp",
        "health": f"{settings.app_base_url}/health",
    })


# ── MCP over Streamable HTTP ───────────────────────────────────────────────────
#
# All MCP traffic (initialize, tools/list, tools/call) goes to POST /mcp.
# MCP Inspector connects with transport type "Streamable HTTP" and URL /mcp.

@app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
async def mcp_endpoint(request: Request):
    """Single endpoint for all MCP Streamable HTTP traffic."""
    return await session_manager.handle_request(
        request.scope, request.receive, request._send
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
