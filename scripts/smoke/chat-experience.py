"""Browser verification against explicit loopback fixtures, never DEV/cloud.

Start backend/tests/browser_app.py on 8089 and the Vite test harness on 5175.
Requires Python Playwright and Chromium locally; does not modify CI/CD.
"""

import json
import urllib.request
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

API = "http://127.0.0.1:8089"
UI = "http://127.0.0.1:5175/tests/browser/app.html"


def get(path, authenticated=False):
    headers = {"Authorization": "Bearer local-browser-test"} if authenticated else {}
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(API + path, headers=headers), timeout=5
        )
    )


def main():
    first = get("/health/local-test-provider")["calls"] + 1
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()
        errors = []
        auth = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on(
            "request",
            lambda r: (
                auth.append(
                    bool(r.headers.get("authorization", "").startswith("Bearer "))
                )
                if "/api/" in r.url
                else None
            ),
        )
        page.goto(UI)
        expect(page.get_by_role("button", name="New chat", exact=True)).to_be_enabled()
        page.get_by_role("button", name="New chat", exact=True).click()
        composer = page.get_by_role("textbox", name="Message", exact=True)
        expect(composer).to_be_enabled()
        composer.fill("Remember blue")
        page.get_by_role("button", name="Send message", exact=True).click()
        page.get_by_role("heading", name=f"Answer {first}", exact=True).wait_for()
        expect(page.get_by_role("button", name="Stop generation")).to_be_visible()
        regenerate = page.get_by_role("button", name="Regenerate", exact=True)
        regenerate.wait_for()
        expect(composer).to_be_enabled()
        page.get_by_role("button", name="Copy code", exact=True).click()
        assert page.evaluate("navigator.clipboard.readText()") == 'print("hello")'
        regenerate.click()
        page.get_by_role("heading", name=f"Answer {first + 1}", exact=True).wait_for()
        expect(page.get_by_role("button", name="Stop generation")).to_be_visible()
        assert (
            page.locator(".chat-message--user .chat-message__body").first.inner_text()
            == "Remember blue"
        )
        assert page.locator('[aria-label="Generating response"]').count() == 1
        assert page.locator(".chat-conversation > article").evaluate_all(
            "nodes => nodes.slice(0, 3).map(n => n.classList.contains('chat-message--user') ? 'user' : 'assistant')"
        ) == ["user", "assistant", "assistant"]
        page.wait_for_selector(".chat-message--superseded")
        expect(composer).to_be_enabled()
        regenerate.click()
        page.get_by_role("heading", name=f"Answer {first + 2}", exact=True).wait_for()
        page.get_by_role("button", name="Stop generation", exact=True).click()
        page.get_by_text(
            "Generation stopped. Partial response saved.", exact=True
        ).wait_for()
        page.reload()
        page.get_by_role("heading", name=f"Answer {first + 2}", exact=True).wait_for()
        expect(composer).to_be_enabled()
        composer.fill("Continue")
        page.get_by_role("button", name="Send message", exact=True).click()
        page.get_by_role("heading", name=f"Answer {first + 3}", exact=True).wait_for()
        expect(composer).to_be_enabled()
        cid = parse_qs(urlsplit(page.url).query)["conversation"][0]
        data = get("/api/conversations/" + cid, True)
        assert [m["status"] for m in data["messages"]] == [
            "completed",
            "superseded",
            "completed",
            "cancelled",
            "completed",
            "completed",
        ]
        assert [m["sequence"] for m in data["messages"]] == list(range(1, 7))
        assert len([m for m in data["messages"] if m["role"] == "user"]) == 2
        provider = get("/health/local-test-provider")
        assert provider["calls"] == first + 3 and first + 2 in provider["closed"]
        contexts = provider["contexts"][-4:]
        assert contexts[0] == contexts[1] == contexts[2]
        assert contexts[3][1]["content"].startswith(f"# Answer {first + 1}")
        assert auth and all(auth)
        assert not errors, errors
        page.screenshot(path="/tmp/openthread-stream-e2e-desktop.png", full_page=True)
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 900})
            page.screenshot(
                path=f"/tmp/openthread-stream-e2e-{width}.png", full_page=True
            )
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        print(
            json.dumps(
                {
                    "local_browser_e2e": "passed",
                    "provider_calls_this_run": 4,
                    "statuses": [m["status"] for m in data["messages"]],
                    "user_messages": 2,
                    "bearer_present_for_all_api_requests": all(auth),
                    "page_errors": len(errors),
                    "mobile_overflow": False,
                }
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
