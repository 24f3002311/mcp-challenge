import os
import json
import hashlib

from starlette.types import ASGIApp, Scope, Receive, Send
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings

EMAIL = "24f3002311@ds.study.iitm.ac.in"

# Store each challenge against its JSON-RPC request ID.
challenges = {}

# Configure the server for deployment behind Render's HTTPS proxy.
mcp = FastMCP(
    "Exam Challenge Server",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


class HeaderCaptureMiddleware:
    """Capture X-Exam-Challenge from incoming MCP tool-call requests."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ):
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }

        # Buffer the body to identify the JSON-RPC request ID.
        body = bytearray()

        while True:
            message = await receive()

            if message["type"] == "http.disconnect":
                return

            body.extend(message.get("body", b""))

            if not message.get("more_body", False):
                break

        request_body = bytes(body)

        try:
            data = json.loads(request_body)

            if (
                isinstance(data, dict)
                and data.get("method") == "tools/call"
                and "id" in data
            ):
                challenge = headers.get("x-exam-challenge")

                if challenge:
                    challenges[str(data["id"])] = challenge

        except (ValueError, TypeError):
            pass

        # Replay the body for the MCP application.
        sent = False

        async def replay_receive():
            nonlocal sent

            if not sent:
                sent = True
                return {
                    "type": "http.request",
                    "body": request_body,
                    "more_body": False,
                }

            return await receive()

        await self.app(scope, replay_receive, send)


@mcp.tool()
def solve_challenge(ctx: Context) -> str:
    """Return the first 16 lowercase hex characters of the required SHA-256."""

    challenge = challenges.pop(str(ctx.request_id), None)

    if not challenge:
        raise ValueError("Missing X-Exam-Challenge header")

    message = f"{challenge}:{EMAIL.strip().lower()}"

    return hashlib.sha256(
        message.encode("utf-8")
    ).hexdigest()[:16]


if __name__ == "__main__":
    import uvicorn

    app = HeaderCaptureMiddleware(
        mcp.streamable_http_app()
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
