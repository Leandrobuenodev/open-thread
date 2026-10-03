// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import { ChatComposer } from "../src/chat/ChatComposer";
import { ChatSidebar } from "../src/chat/ChatSidebar";
import { ChatMessage } from "../src/chat/ChatMessage";
import {
  uploadAttachment,
  updateConversation,
  createProject,
  listLibrary,
  editResponse,
} from "../src/api";
let root: Root, container: HTMLDivElement;
class Recognition {
  static current: Recognition;
  lang = "";
  continuous = false;
  interimResults = false;
  onstart: any;
  onend: any;
  onerror: any;
  onresult: any;
  start = vi.fn(() => this.onstart?.());
  stop = vi.fn(() => this.onend?.());
  abort = vi.fn(() => this.onend?.());
  constructor() {
    Recognition.current = this;
  }
}
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  if (!URL.createObjectURL)
    Object.defineProperty(URL, "createObjectURL", {
      value: vi.fn(),
      configurable: true,
    });
  if (!URL.revokeObjectURL)
    Object.defineProperty(URL, "revokeObjectURL", {
      value: vi.fn(),
      configurable: true,
    });
  (window as any).SpeechRecognition = Recognition;
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  delete (window as any).SpeechRecognition;
  vi.restoreAllMocks();
});
function button(name: string) {
  return [...container.querySelectorAll<HTMLButtonElement>("button")].find(
    (b) => b.getAttribute("aria-label") === name || b.textContent === name,
  )!;
}
async function composer(change = vi.fn(), submit = vi.fn()) {
  await act(async () =>
    root.render(
      <ChatComposer
        input="draft"
        isLoading={false}
        onChange={change}
        onSubmit={submit}
      />,
    ),
  );
  return { change, submit };
}
it("records, appends transcript to composer and never sends", async () => {
  const { change, submit } = await composer();
  await act(async () => button("Start microphone").click());
  expect(container.textContent).toContain("Recording…");
  expect(Recognition.current.lang).toBe(navigator.language);
  await act(async () =>
    Recognition.current.onresult({
      resultIndex: 0,
      results: [{ isFinal: true, 0: { transcript: "spoken text" } }],
    }),
  );
  expect(change).toHaveBeenCalledWith("draft spoken text");
  expect(submit).not.toHaveBeenCalled();
  await act(async () => button("Finish recording").click());
  expect(container.textContent).not.toContain("Recording…");
});
it("handles permission denied and permits retry", async () => {
  await composer();
  await act(async () => button("Start microphone").click());
  await act(async () => {
    Recognition.current.onerror({ error: "not-allowed" });
    Recognition.current.onend();
  });
  expect(container.textContent).toContain("Microphone permission denied.");
  await act(async () => button("Start microphone").click());
  expect(container.textContent).toContain("Recording…");
});
it("cancel ignores late transcripts and aborts recording", async () => {
  const { change, submit } = await composer();
  await act(async () => button("Start microphone").click());
  const recognition = Recognition.current;
  await act(async () => button("Cancel recording").click());
  await act(async () =>
    recognition.onresult({
      resultIndex: 0,
      results: [{ isFinal: true, 0: { transcript: "late" } }],
    }),
  );
  expect(change).not.toHaveBeenCalled();
  expect(submit).not.toHaveBeenCalled();
  expect(recognition.abort).toHaveBeenCalledOnce();
});
it("unsupported browser leaves keyboard composer usable", async () => {
  delete (window as any).SpeechRecognition;
  await composer();
  expect(button("Start microphone").disabled).toBe(true);
  expect(container.textContent).toContain("Speech unavailable");
  expect(button("Send message").disabled).toBe(false);
});
it("recognition errors and start failures remain editable", async () => {
  await composer();
  await act(async () => button("Start microphone").click());
  await act(async () => {
    Recognition.current.onerror({ error: "no-speech" });
    Recognition.current.onend();
  });
  expect(container.textContent).toContain("No speech detected.");
});
it("image preview permits image-only send and revoke on removal", async () => {
  const create = vi
    .spyOn(URL, "createObjectURL")
    .mockReturnValue("blob:preview");
  const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const submit = vi.fn(),
    image = vi.fn(),
    file = new File(["png"], "photo.png", { type: "image/png" });
  await act(async () =>
    root.render(
      <ChatComposer
        input=""
        image={file}
        onImage={image}
        isLoading={false}
        onChange={() => {}}
        onSubmit={submit}
      />,
    ),
  );
  expect(create).toHaveBeenCalledWith(file);
  expect(container.querySelector("img")?.getAttribute("src")).toBe(
    "blob:preview",
  );
  expect(button("Send message").disabled).toBe(false);
  await act(async () =>
    container
      .querySelector("form")!
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
  expect(submit).toHaveBeenCalledOnce();
  await act(async () => button("Remove image").click());
  expect(image).toHaveBeenCalledWith(null);
  await act(async () =>
    root.render(
      <ChatComposer
        input=""
        isLoading={false}
        onChange={() => {}}
        onSubmit={submit}
      />,
    ),
  );
  expect(revoke).toHaveBeenCalledWith("blob:preview");
});
it("invalid image selection is rejected before upload", async () => {
  const select = vi.fn();
  await act(async () =>
    root.render(
      <ChatComposer
        input=""
        onImage={select}
        isLoading={false}
        onChange={() => {}}
        onSubmit={() => {}}
      />,
    ),
  );
  const input = container.querySelector('input[type="file"]')!;
  Object.defineProperty(input, "files", {
    value: [new File(["<svg/>"], "fake.png", { type: "image/svg+xml" })],
  });
  await act(async () =>
    input.dispatchEvent(new Event("change", { bubbles: true })),
  );
  expect(select).not.toHaveBeenCalled();
  expect(container.textContent).toContain("Use PNG, JPEG or WebP up to 2 MiB.");
});
it("user Edit action and cancel composer are explicit", async () => {
  const edit = vi.fn();
  await act(async () =>
    root.render(
      <ChatMessage
        message={{ id: "u", role: "user", text: "original" }}
        onEdit={edit}
      />,
    ),
  );
  await act(async () => button("Edit").click());
  expect(edit).toHaveBeenCalledOnce();
  const cancel = vi.fn();
  await act(async () =>
    root.render(
      <ChatComposer
        input="edited"
        editing
        onCancelEdit={cancel}
        isLoading={false}
        onChange={() => {}}
        onSubmit={() => {}}
      />,
    ),
  );
  expect(container.textContent).toContain("subsequent messages");
  await act(async () => button("Cancel edit").click());
  expect(cancel).toHaveBeenCalledOnce();
});
it("persistent sidebar selects pinned/project conversations and updates metadata", async () => {
  const select = vi.fn(),
    meta = vi.fn(),
    rename = vi.fn(),
    remove = vi.fn();
  vi.spyOn(window, "prompt").mockReturnValue("Renamed");
  vi.spyOn(window, "confirm").mockReturnValue(true);
  await act(async () =>
    root.render(
      <ChatSidebar
        authError={null}
        isCollapsed={false}
        isNewConversationDisabled={false}
        isSigningOut={false}
        onNewConversation={() => {}}
        onSignOut={async () => {}}
        onToggleCollapse={() => {}}
        onSelectMessage={() => {}}
        messages={[]}
        onOpenSearch={() => {}}
        userName="Test"
        onSelectConversation={select}
        conversations={[
          {
            id: "c",
            title: "Chat",
            created_at: "now",
            updated_at: "now",
            is_pinned: true,
            project_id: "p",
          },
        ]}
        pinnedChats={[{ id: "c", title: "Chat", messageId: "c" }]}
        projects={[
          {
            id: "p",
            name: "Project",
            chats: [{ id: "c", title: "Chat", messageId: "c" }],
          },
        ]}
        onMetadata={meta}
        onRenameProject={rename}
        onDeleteProject={remove}
      />,
    ),
  );
  expect(container.textContent).not.toContain("session only");
  await act(async () => button("Unpin conversation: Chat").click());
  expect(meta).toHaveBeenCalledWith("c", { is_pinned: false });
  const chooser = container.querySelector("select")!;
  await act(async () => {
    chooser.value = "";
    chooser.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(meta).toHaveBeenCalledWith("c", { project_id: null });
  await act(async () => button("Rename project: Project").click());
  expect(rename).toHaveBeenCalledWith("p", "Renamed");
  await act(async () => button("Delete project: Project").click());
  expect(remove).toHaveBeenCalledWith("p");
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-controls="chat-pinned"]')!
      .click(),
  );
  await act(async () =>
    container.querySelector<HTMLButtonElement>("#chat-pinned button")!.click(),
  );
  expect(select).toHaveBeenCalledWith("c");
});
it("workspace requests use bearer auth and explicit payloads", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
    async () =>
      new Response(JSON.stringify({ id: "a" }), {
        status: 201,
        headers: { "content-type": "application/json" },
      }),
  );
  const file = new File(["image"], "x.png", { type: "image/png" });
  await uploadAttachment("c", file, "token");
  let request = fetchMock.mock.calls.at(-1)![1]!;
  expect(request.body).toBe(file);
  expect((request.headers as any).Authorization).toBe("Bearer token");
  expect((request.headers as any)["Content-Type"]).toBe("image/png");
  await updateConversation("c", { is_pinned: true, project_id: "p" }, "token");
  request = fetchMock.mock.calls.at(-1)![1]!;
  expect(request.method).toBe("PATCH");
  expect(JSON.parse(request.body as string)).toEqual({
    is_pinned: true,
    project_id: "p",
  });
  await createProject("Name", "token");
  expect(JSON.parse(fetchMock.mock.calls.at(-1)![1]!.body as string)).toEqual({
    name: "Name",
  });
  await listLibrary("token", 50);
  expect(fetchMock.mock.calls.at(-1)![0]).toContain("/library?offset=50");
});
it("edit uses authenticated existing SSE pipeline", async () => {
  const enc = new TextEncoder(),
    events = vi.fn();
  const u = { id: "u", role: "user", content: "edited", status: "pending" },
    a = { id: "a", role: "assistant", content: "", status: "pending" };
  const frames = `event: start\ndata: ${JSON.stringify({ user: u, assistant: a })}\n\nevent: delta\ndata: {"id":"a","text":"answer"}\n\nevent: done\ndata: ${JSON.stringify({ assistant: { ...a, content: "answer", status: "completed" } })}\n\n`;
  const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(enc.encode(frames), {
      headers: { "content-type": "text/event-stream" },
    }),
  );
  await editResponse("edited", "old", "token", "c", events);
  expect(mock.mock.calls[0][0]).toContain("/conversations/c/messages/old/edit");
  expect(JSON.parse(mock.mock.calls[0][1]!.body as string)).toEqual({
    message: "edited",
  });
  expect(events.mock.calls.map((c) => c[0].type)).toEqual([
    "start",
    "delta",
    "done",
  ]);
});

it("supports prefixed speech API and handles start exceptions", async () => {
  delete (window as any).SpeechRecognition;
  (window as any).webkitSpeechRecognition = Recognition;
  await composer();
  expect(button("Start microphone").disabled).toBe(false);
  delete (window as any).webkitSpeechRecognition;
  class FailingRecognition extends Recognition {
    start = vi.fn(() => {
      throw new Error("device unavailable");
    });
  }
  (window as any).SpeechRecognition = FailingRecognition;
  await composer();
  await act(async () => button("Start microphone").click());
  expect(container.textContent).toContain("Unable to start microphone.");
  expect(container.querySelector("textarea")!.disabled).toBe(false);
});
