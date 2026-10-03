"""Loopback-only browser fixture; synthetic identity/provider, never a cloud call."""

import asyncio
import json

import httpx
from app.auth import AuthenticatedUser, get_current_user
from app.dependencies import get_foundry_client
from app.foundry import FoundryClient, FoundrySettings
from app.main import create_app
from fastapi import HTTPException, Request

app = create_app()
calls = []
closed = []


async def local_identity(request: Request):
    if request.headers.get("Authorization") != "Bearer local-browser-test":
        raise HTTPException(401, "Local test authorization required.")
    return AuthenticatedUser("local-browser-user", "local-test-tenant")


class Deltas(httpx.AsyncByteStream):
    def __init__(self, number):
        self.number = number

    async def __aiter__(self):
        parts = [
            f"# Answer {self.number}\n\n",
            "**Remember blue** and *context*.\n\n",
            "- One\n- Two\n\n",
            "> Quote\n\n",
            "[Link](https://example.com) and `inline`.\n\n",
            "```python\n",
            'print("hello")\n',
            "```\n\n",
            "| A | B |\n|---|---|\n| 1 | 2 |\n",
        ]
        for part in parts:
            yield (
                "data: "
                + json.dumps(
                    {"choices": [{"delta": {"content": part}, "finish_reason": None}]}
                )
                + "\n\n"
            ).encode()
            await asyncio.sleep(0.15)
        yield b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'

    async def aclose(self):
        closed.append(self.number)


def provider(request):
    calls.append(json.loads(request.content))
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, stream=Deltas(len(calls))
    )


client = FoundryClient(
    FoundrySettings(
        "https://local-fake.openai.azure.com", "local-test", "local-fake-key"
    ),
    transport=httpx.MockTransport(provider),
)
app.dependency_overrides[get_current_user] = local_identity
app.dependency_overrides[get_foundry_client] = lambda: client


@app.get("/health/local-test-provider")
def local_test_provider():
    return {
        "calls": len(calls),
        "closed": closed,
        "contexts": [
            [
                {
                    "role": m["role"],
                    "content": m["content"]
                    if isinstance(m["content"], str)
                    else [
                        {
                            "type": part["type"],
                            **(
                                {"text": part["text"]}
                                if part["type"] == "text"
                                else {"image_present": True}
                            ),
                        }
                        for part in m["content"]
                    ],
                }
                for m in call["messages"]
            ]
            for call in calls
        ],
    }
