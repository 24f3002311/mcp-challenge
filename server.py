import os
import json
import hashlib

from starlette.types import ASGIApp, Scope, Receive, Send
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings

EMAIL = "24f3002311@ds.study.iitm.ac.in"

# Associate each JSON-RPC request ID with its HTTP challenge.
challenges = {}

mcp = FastMCP("Exam Challenge Server")


class HeaderCaptureMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ):
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }

        # Buffer the incoming body so we can inspect the JSON-RPC ID.
        body = b""
        more_body = True

        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        try:
            data = json.loads(body)
            if (
                data.get("method") == "tools/call"
                and headers.get("x-exam-challenge")
                and "id" in data
            ):
                challenges[str(data["id"])] = headers["x-exam-challenge"]
        except (ValueError, AttributeError, TypeError):
            pass

        # Replay the body for the MCP application.
        sent = False

        async def replay_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay_receive, send)


@mcp.tool()
def solve_challenge(ctx: Context) -> str:
    """Hash the challenge from the current HTTP tool-call headers."""

    challenge = challenges.pop(str(ctx.request_id), None)

    if not challenge:
        raise ValueError("Challenge header missing for this tool call")

    message = f"{challenge}:{EMAIL}"
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    import uvicorn

    app = HeaderCaptureMiddleware(
    mcp.streamable_http_app(
        host="mcp-challenge-ktm5.onrender.com"
    )
)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
