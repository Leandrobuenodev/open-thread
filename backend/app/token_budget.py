"""Conservative byte-level token estimate for the small DEV deployment."""

from fastapi import HTTPException

from app.protection import ChatLimits, positive_integer


def text_bytes(content):
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    return sum(len(p.get("text", "").encode("utf-8")) for p in content)


def input_cost(content):
    # Images are normalized to <=256px: <=64 32px patches, multiplier 1.62.
    return text_bytes(content) + (
        sum(104 for p in content if p.get("type") == "image_url")
        if isinstance(content, list)
        else 0
    )


class ContextBudget:
    def __init__(self):
        self.total = positive_integer("CHAT_TOKEN_BUDGET", 1000)
        self.margin = positive_integer("CHAT_TOKEN_SAFETY_MARGIN", 100)
        self.output = ChatLimits.from_environment().output_tokens
        if (
            self.total - self.margin
            < self.output + 64 + 8 + ChatLimits.from_environment().message_bytes
        ):
            raise ValueError(
                "CHAT_TOKEN_BUDGET must accommodate input, output and safety reserves."
            )

    def estimate(self, messages):
        # UTF-8 byte count is a deliberately conservative upper estimate for text
        # BPE tokens. Account for roles/framing and any system/instruction message.
        return 64 + self.output + sum(8 + input_cost(m["content"]) for m in messages)

    def trim(self, messages, max_bytes):
        messages = list(messages)
        while len(messages) > 1 and (
            self.estimate(messages) > self.total - self.margin
            or sum(text_bytes(m["content"]) for m in messages) > max_bytes
        ):
            messages.pop(0)
        while len(messages) > 1 and messages[0]["role"] == "assistant":
            messages.pop(0)
        if self.estimate(messages) > self.total - self.margin:
            raise HTTPException(422, "Message exceeds the configured token budget.")
        return messages
