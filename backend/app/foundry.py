import asyncio
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT_SECONDS = 30.0


class FoundryError(RuntimeError):
    """A Foundry request did not produce a usable text response."""


class FoundryThrottled(FoundryError):
    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__("Too many requests. Please try again later.")
        self.retry_after = retry_after


def throttling_delay(headers: httpx.Headers) -> int | None:
    """Normalize only usable delay headers; never forward arbitrary upstream text."""
    raw = headers.get("retry-after", "")
    if raw.isascii() and raw.isdigit() and len(raw) <= 9:
        return max(1, int(raw))
    if raw:
        try:
            retry_at = parsedate_to_datetime(raw)
            if retry_at.tzinfo is not None:
                return max(
                    1,
                    math.ceil((retry_at - datetime.now(timezone.utc)).total_seconds()),
                )
        except (ValueError, TypeError, OverflowError):
            pass
    raw_ms = headers.get("retry-after-ms", "")
    if raw_ms.isascii() and raw_ms.isdigit() and len(raw_ms) <= 12:
        return max(1, math.ceil(int(raw_ms) / 1000))
    return None


class FoundryConfigurationError(RuntimeError):
    """Required Foundry configuration is missing or invalid."""


@dataclass(frozen=True)
class FoundrySettings:
    endpoint: str
    deployment: str
    api_key: str = field(repr=False)

    @classmethod
    def from_environment(cls) -> "FoundrySettings":
        names = ("FOUNDRY_ENDPOINT", "FOUNDRY_DEPLOYMENT", "FOUNDRY_API_KEY")
        values = {name: os.getenv(name, "").strip() for name in names}
        missing = [name for name in names if not values[name]]
        if missing:
            raise FoundryConfigurationError(
                "Missing Foundry configuration: " + ", ".join(missing) + "."
            )
        return cls(*(values[name] for name in names))

    def __post_init__(self) -> None:
        # Accept only an Azure resource root, never a project URL or another host.
        try:
            url = urlsplit(self.endpoint)
            valid = (
                not any(
                    character.isspace() or ord(character) < 32 or ord(character) == 127
                    for character in self.endpoint
                )
                and url.scheme == "https"
                and url.hostname is not None
                and url.hostname.endswith(
                    (".services.ai.azure.com", ".openai.azure.com")
                )
                and url.port in (None, 443)
                and url.username is None
                and url.password is None
                and url.path in ("", "/")
                and not url.query
                and not url.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise FoundryConfigurationError(
                "FOUNDRY_ENDPOINT must be an HTTPS Azure Foundry resource root "
                "ending in .services.ai.azure.com or .openai.azure.com."
            )
        if not self.deployment.strip() or not self.api_key.strip():
            raise FoundryConfigurationError(
                "FOUNDRY_DEPLOYMENT and FOUNDRY_API_KEY must be configured."
            )
        if not self.api_key.isascii() or any(
            ord(character) < 33 or ord(character) == 127 for character in self.api_key
        ):
            raise FoundryConfigurationError(
                "FOUNDRY_API_KEY must be a valid ASCII credential without whitespace."
            )


class FoundryClient:
    """Concrete, API-key authenticated Foundry v1 Chat Completions client.

    Owns one async HTTP connection pool. No automatic retries or conversation
    storage. Settings are checked on a chat call so healths work before setup.
    """

    def __init__(
        self,
        settings: FoundrySettings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_output_tokens: int = 256,
    ) -> None:
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive.")
        self._max_output_tokens = max_output_tokens
        self._settings = settings
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=5.0),
            transport=transport or httpx.AsyncHTTPTransport(retries=0),
            follow_redirects=False,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def generate_reply(self, message: str | list[dict[str, str]]) -> str:
        settings = self._settings or FoundrySettings.from_environment()
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                response = await self._http.post(
                    settings.endpoint.rstrip("/") + "/openai/v1/chat/completions",
                    headers={"api-key": settings.api_key},
                    json={
                        "model": settings.deployment,
                        "messages": (
                            [{"role": "user", "content": message}]
                            if isinstance(message, str)
                            else message
                        ),
                        "stream": False,
                        "max_completion_tokens": self._max_output_tokens,
                    },
                )
                response.raise_for_status()
        except (TimeoutError, httpx.TimeoutException):
            logger.warning("Foundry request timed out.")
            raise FoundryError("Microsoft Foundry request timed out.") from None
        except httpx.HTTPStatusError as exc:
            # Never log response bodies, URLs, headers, credentials or prompts.
            logger.warning("Foundry upstream status: %s", exc.response.status_code)
            if exc.response.status_code == 429:
                raise FoundryThrottled(throttling_delay(exc.response.headers)) from None
            raise FoundryError("Microsoft Foundry request failed.") from None
        except httpx.RequestError:
            logger.warning("Foundry connection failed.")
            raise FoundryError("Microsoft Foundry connection failed.") from None

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError
            return content.strip()
        except (ValueError, KeyError, IndexError, TypeError):
            raise FoundryError(
                "Microsoft Foundry returned an invalid text response."
            ) from None

    async def stream_reply(self, messages):
        """Yield provider SSE deltas as they arrive; require a final marker."""
        import json

        settings = self._settings or FoundrySettings.from_environment()
        saw_finish = False
        received_text = False
        total_bytes = 0
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                async with self._http.stream(
                    "POST",
                    settings.endpoint.rstrip("/") + "/openai/v1/chat/completions",
                    headers={"api-key": settings.api_key},
                    json={
                        "model": settings.deployment,
                        "messages": messages,
                        "stream": True,
                        "max_completion_tokens": self._max_output_tokens,
                    },
                ) as response:
                    response.raise_for_status()
                    if "text/event-stream" not in response.headers.get(
                        "content-type", ""
                    ):
                        raise FoundryError(
                            "Microsoft Foundry returned an invalid stream."
                        )
                    async for line in response.aiter_lines():
                        total_bytes += len(line.encode("utf-8"))
                        if total_bytes > 262_144:
                            raise FoundryError(
                                "Microsoft Foundry stream exceeded its safety limit."
                            )
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            if not saw_finish or not received_text:
                                raise FoundryError(
                                    "Microsoft Foundry returned an incomplete stream."
                                )
                            return
                        try:
                            payload = json.loads(data)
                            if "error" in payload:
                                raise ValueError
                            choices = payload["choices"]
                            if not choices:  # Optional provider usage-only event.
                                continue
                            choice = choices[0]
                            reason = choice.get("finish_reason")
                            if reason is not None:
                                if reason not in ("stop", "length"):
                                    raise ValueError
                                saw_finish = True
                            text = choice.get("delta", {}).get("content")
                            if text is not None and not isinstance(text, str):
                                raise ValueError
                        except (ValueError, KeyError, IndexError, TypeError):
                            raise FoundryError(
                                "Microsoft Foundry returned an invalid stream."
                            ) from None
                        if text:
                            received_text = True
                            yield text
            raise FoundryError("Microsoft Foundry stream ended unexpectedly.")
        except (TimeoutError, httpx.TimeoutException):
            raise FoundryTimeout() from None
        except httpx.HTTPStatusError as exc:
            logger.warning("Foundry upstream status: %s", exc.response.status_code)
            if exc.response.status_code == 429:
                raise FoundryThrottled(throttling_delay(exc.response.headers)) from None
            raise FoundryError("Microsoft Foundry request failed.") from None
        except httpx.RequestError:
            raise FoundryError("Microsoft Foundry connection failed.") from None


class FoundryTimeout(FoundryError):
    def __init__(self):
        super().__init__("Microsoft Foundry request timed out.")
