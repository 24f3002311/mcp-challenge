import asyncio
import hashlib
import json

import httpx

URL = "http://127.0.0.1:8000/mcp"
CHALLENGE = "0123456789abcdef0123456789abcdef"
EMAIL = "24f3002311@ds.study.iitm.ac.in"


async def main():
    async with httpx.AsyncClient() as client:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-03-26",
        }

        # 1. Initialize the MCP connection.
        response = await client.post(
            URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ubuntu-test",
                        "version": "1.0",
                    },
                },
            },
        )

        print("INITIALIZE:", response.status_code)
        print(response.text)

        if response.status_code != 200:
            return

        session_id = response.headers.get("mcp-session-id")
        headers["MCP-Session-Id"] = session_id

        # 2. Send the initialized notification.
        notification_headers = dict(headers)
        notification_headers["Accept"] = "application/json, text/event-stream"

        await client.post(
            URL,
            headers=notification_headers,
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )

        # 3. List available tools.
        response = await client.post(
            URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )

        print("\nTOOLS/LIST:", response.status_code)
        print(response.text)

        # 4. Call the tool with the challenge in the HTTP header.
        call_headers = dict(headers)
        call_headers["X-Exam-Challenge"] = CHALLENGE

        response = await client.post(
            URL,
            headers=call_headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "solve_challenge",
                    "arguments": {},
                },
            },
        )

        print("\nTOOLS/CALL:", response.status_code)
        print(response.text)

        expected = hashlib.sha256(
            f"{CHALLENGE}:{EMAIL}".encode()
        ).hexdigest()[:16]

        print("\nEXPECTED ANSWER:", expected)
        print("Check whether the tool text matches this value.")


if __name__ == "__main__":
    asyncio.run(main())
