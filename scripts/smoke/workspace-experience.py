"""Five features together in Chromium; loopback identity/provider and speech fixture.

Use backend/tests/browser_app.py on 8089 and Vite test entry on 5175.
No Azure call, paid inference, actual bearer token or microphone audio.
"""

import base64
import json
import urllib.request
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

API = "http://127.0.0.1:8089"
UI = "http://127.0.0.1:5175/tests/browser/app.html"


def get(path, authenticated=False):
    headers = {"Authorization": "Bearer local-browser-test"} if authenticated else {}
    with urllib.request.urlopen(
        urllib.request.Request(API + path, headers=headers), timeout=5
    ) as response:
        return json.load(response)


SPEECH = """
class LocalSpeech {
 constructor(){ window.localSpeech=this; }
 start(){this.onstart?.();}
 stop(){this.onend?.();}
 abort(){this.onend?.();}
}
window.SpeechRecognition=LocalSpeech;
"""


def main():
    suffix = uuid4().hex[:6]
    prompt = "Describe blue " + suffix
    project_name = "Images project " + suffix
    renamed_name = "Renamed project " + suffix
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        context.add_init_script(SPEECH)
        page = context.new_page()
        errors, auth = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "request",
            lambda request: (
                auth.append(
                    bool(request.headers.get("authorization", "").startswith("Bearer "))
                )
                if "/api/" in request.url
                else None
            ),
        )
        page.goto(UI)
        new_chat = page.get_by_role("button", name="New chat", exact=True)
        expect(new_chat).to_be_enabled()
        new_chat.click()
        composer = page.get_by_role("textbox", name="Message", exact=True)
        expect(composer).to_be_enabled()
        cid = parse_qs(urlsplit(page.url).query)["conversation"][0]
        before = get("/health/local-test-provider")["calls"]
        page.get_by_role("button", name="Start microphone").click()
        expect(page.get_by_text("Recording…", exact=True)).to_be_visible()
        page.evaluate(
            "text => {localSpeech.onresult({resultIndex:0,results:[{isFinal:true,0:{transcript:text}}]});localSpeech.onend();}",
            prompt,
        )
        expect(composer).to_have_value(prompt)
        assert get("/health/local-test-provider")["calls"] == before
        # Actual PNG bytes, selected through the browser file input.
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4h8AAAAASUVORK5CYII="
        )
        page.get_by_label("Choose image").set_input_files(
            {"name": "blue.png", "mimeType": "image/png", "buffer": png}
        )
        expect(page.get_by_alt_text("Image preview")).to_be_visible()
        page.get_by_role("button", name="Send message", exact=True).click()
        expect(composer).to_be_enabled(timeout=10000)
        expect(
            page.get_by_role("button", name="Regenerate", exact=True)
        ).to_be_visible()
        expect(page.get_by_alt_text("blue.png")).to_be_visible()
        detail = get("/api/conversations/" + cid, True)
        assert detail["messages"][0]["attachments"]
        calls = get("/health/local-test-provider")
        assert calls["contexts"][-1][-1]["content"][1]["image_present"]
        page.get_by_role("button", name="Create project", exact=True).click()
        page.get_by_role("textbox", name="Project name", exact=True).fill(project_name)
        page.get_by_role("dialog").get_by_role(
            "button", name="Create project", exact=True
        ).click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        choose = page.get_by_label(f"Project for conversation: {prompt}", exact=True)
        choose.select_option(label=project_name)
        expect(choose).to_be_enabled()
        page.get_by_role(
            "button", name=f"Pin conversation: {prompt}", exact=True
        ).click()
        expect(
            page.get_by_role("button", name=f"Unpin conversation: {prompt}", exact=True)
        ).to_be_visible()
        page.reload()
        expect(composer).to_be_enabled()
        expect(page.get_by_alt_text("blue.png")).to_be_visible()
        expect(
            page.get_by_label(f"Project for conversation: {prompt}", exact=True)
        ).to_have_value(get("/api/conversations/" + cid, True)["project_id"])
        expect(
            page.get_by_role("button", name=f"Unpin conversation: {prompt}", exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Edit", exact=True).click()
        expect(composer).to_have_value(prompt)
        composer.fill("Describe the edited image")
        page.get_by_role("button", name="Send message", exact=True).click()
        expect(
            page.get_by_role("button", name="Stop generation", exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Stop generation", exact=True).click()
        expect(
            page.get_by_text("Generation stopped. Partial response saved.", exact=True)
        ).to_be_visible()
        page.reload()
        expect(composer).to_be_enabled()
        detail = get("/api/conversations/" + cid, True)
        assert detail["messages"][0]["status"] == "superseded"
        assert detail["messages"][-2]["replaces_id"] == detail["messages"][0]["id"]
        assert detail["messages"][-2]["attachments"]
        assert detail["messages"][-1]["status"] == "cancelled"
        page.get_by_role("button", name="Regenerate", exact=True).click()
        expect(composer).to_be_enabled(timeout=10000)
        expect(page.get_by_role("button", name="Edit", exact=True)).to_be_enabled()
        composer.fill("Continue with context")
        page.get_by_role("button", name="Send message", exact=True).click()
        expect(composer).to_be_enabled(timeout=10000)
        detail = get("/api/conversations/" + cid, True)
        assert detail["messages"][-1]["status"] == "completed"
        assert all(
            message["content"] != prompt
            for message in get("/health/local-test-provider")["contexts"][-1]
            if isinstance(message["content"], str)
        )
        # Rename, detach on delete, retain chat/pin; unpin removes empty section.
        page.once("dialog", lambda dialog: dialog.accept(renamed_name))
        page.get_by_role(
            "button", name=f"Rename project: {project_name}", exact=True
        ).click()
        expect(
            page.get_by_role(
                "button", name=f"Delete project: {renamed_name}", exact=True
            )
        ).to_be_visible()
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role(
            "button", name=f"Delete project: {renamed_name}", exact=True
        ).click()
        expect(
            page.get_by_role(
                "button", name=f"Delete project: {renamed_name}", exact=True
            )
        ).to_have_count(0)
        assert get("/api/conversations/" + cid, True)["project_id"] is None
        page.get_by_role(
            "button", name=f"Unpin conversation: {prompt}", exact=True
        ).click()
        expect(page.get_by_role("region", name="Pinned chats")).to_have_count(0)
        # Microphone errors and cancel do not invoke the provider.
        count = get("/health/local-test-provider")["calls"]
        page.get_by_role("button", name="Start microphone").click()
        page.evaluate("localSpeech.onerror({error:'not-allowed'});localSpeech.onend();")
        expect(
            page.get_by_text("Microphone permission denied.", exact=True)
        ).to_be_visible()
        assert get("/health/local-test-provider")["calls"] == count
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.get_by_role("button", name="Start microphone")).to_be_visible()
        target = page.get_by_role("button", name="Start microphone").bounding_box()
        assert target and target["width"] >= 44 and target["height"] >= 44
        page.screenshot(path="/tmp/openthread-workspace-mobile.png", full_page=True)
        assert auth and all(auth)
        assert not errors, errors
        print(
            json.dumps(
                {
                    "features": 5,
                    "browser": "Chromium",
                    "inference": "local fake SSE provider",
                    "speech": "deterministic browser fixture",
                    "authenticated_requests": len(auth),
                    "provider_calls": count - before,
                    "reload": True,
                    "edit_stop_regenerate": True,
                    "projects_delete_retains_chat": True,
                    "mobile_touch_target": True,
                }
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
