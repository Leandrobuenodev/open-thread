"""Requested 14-step local browser flow over actual Azurite Table + Blob.
Uses only backend/tests/browser_app.py synthetic identity/provider on loopback.
"""

import base64
import importlib.util
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

spec = importlib.util.spec_from_file_location(
    "workspace_smoke", Path(__file__).with_name("workspace-experience.py")
)
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)
get = workspace.get

# Hyphenated smoke module is loaded explicitly; no cloud credentials are accessed.


def main():
    suffix = uuid4().hex[:6]
    title = "Remember blue " + suffix
    project = "Storage project " + suffix
    url = "http://127.0.0.1:5175/tests/browser/app.html"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        new = page.get_by_role("button", name="New chat", exact=True)
        expect(new).to_be_enabled()
        new.click()
        composer = page.get_by_role("textbox", name="Message", exact=True)
        expect(composer).to_be_enabled()
        cid = parse_qs(urlsplit(page.url).query)["conversation"][0]

        def send(text):
            composer.fill(text)
            page.get_by_role("button", name="Send message", exact=True).click()
            expect(composer).to_be_enabled(timeout=10000)

        send(title)
        send("Which color did I mention?")
        page.reload()
        expect(composer).to_be_enabled()
        assert len(get("/api/conversations/" + cid, True)["messages"]) == 4
        page.get_by_role(
            "button", name="Pin conversation: " + title, exact=True
        ).click()
        expect(
            page.get_by_role("button", name="Unpin conversation: " + title, exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Create project", exact=True).click()
        page.get_by_role("textbox", name="Project name").fill(project)
        page.get_by_role("dialog").get_by_role(
            "button", name="Create project", exact=True
        ).click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        choose = page.get_by_label("Project for conversation: " + title, exact=True)
        choose.select_option(label=project)
        expect(choose).to_be_enabled()
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4h8AAAAASUVORK5CYII="
        )
        page.get_by_label("Choose image").set_input_files(
            {"name": "storage.png", "mimeType": "image/png", "buffer": png}
        )
        expect(page.get_by_alt_text("Image preview")).to_be_visible()
        send("Describe this image")
        expect(page.get_by_alt_text("storage.png")).to_be_visible()
        send("Continue using the image context")
        page.get_by_role("button", name="Regenerate", exact=True).click()
        expect(composer).to_be_enabled(timeout=10000)
        detail = get("/api/conversations/" + cid, True)
        prompt = next(
            m for m in detail["messages"] if m["content"] == "Describe this image"
        )
        page.locator("#message-" + prompt["id"]).get_by_role(
            "button", name="Edit", exact=True
        ).click()
        expect(composer).to_have_value("Describe this image")
        composer.fill("Edited image request")
        count = get("/health/local-test-provider")["calls"]
        page.get_by_role("button", name="Send message", exact=True).click()
        page.get_by_role("heading", name=f"Answer {count + 1}", exact=True).wait_for()
        page.get_by_role("button", name="Stop generation", exact=True).click()
        expect(
            page.get_by_text("Generation stopped. Partial response saved.", exact=True)
        ).to_be_visible()
        page.reload()
        expect(composer).to_be_enabled()
        detail = get("/api/conversations/" + cid, True)
        assert detail["is_pinned"] and detail["project_id"]
        assert (
            detail["messages"][-1]["status"] == "cancelled"
            and detail["messages"][-1]["content"]
        )
        assert (
            detail["messages"][-2]["replaces_id"] == prompt["id"]
            and detail["messages"][-2]["attachments"]
        )
        assert all(m["status"] == "superseded" for m in detail["messages"][4:-2])
        assert all(m["status"] == "completed" for m in detail["messages"][:4])
        expect(
            page.get_by_role("button", name="Unpin conversation: " + title, exact=True)
        ).to_be_visible()
        # A completely new browser session rehydrates the same owner from the test auth fixture.
        another = browser.new_context()
        fresh = another.new_page()
        fresh.goto(page.url)
        expect(fresh.get_by_role("textbox", name="Message", exact=True)).to_be_enabled()
        expect(
            fresh.get_by_role("button", name="Unpin conversation: " + title, exact=True)
        ).to_be_visible()
        assert not errors, errors
        print(
            json.dumps(
                {
                    "steps": 14,
                    "storage": "Azurite Table + private Blob",
                    "several_messages": True,
                    "reloads": 2,
                    "new_browser_session": True,
                    "pin_project_image_regenerate_edit_stop": True,
                    "partial_saved": True,
                    "page_errors": 0,
                }
            )
        )
        another.close()
        browser.close()


if __name__ == "__main__":
    main()
