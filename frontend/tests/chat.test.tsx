// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { InteractionStatus } from "@azure/msal-browser";
const mocks = vi.hoisted(() => ({
  auth: {
    account: { name: "Test" } as any,
    authError: null,
    inProgress: "none",
    signIn: vi.fn(),
    getAccessToken: vi.fn(),
  },
  send: vi.fn(),
  stream: vi.fn(),
  regen: vi.fn(),
  partial: "",
  create: vi.fn(),
  list: vi.fn(),
  get: vi.fn(),
  remove: vi.fn(),
  rows: [] as any[],
  detail: {} as Record<string, any>,
  landing: null as any,
  page: null as any,
}));
vi.mock("../src/auth/AuthProvider", () => ({ useEntraAuth: () => mocks.auth }));
vi.mock("../src/home/HomePage", () => ({
  HomePage: (props: any) => {
    mocks.landing = props;
    return <p>Landing</p>;
  },
}));
vi.mock("../src/api", () => ({
  listProjects: vi.fn().mockResolvedValue([]),
  listLibrary: vi.fn().mockResolvedValue([]),
  sendChatMessage: mocks.send,
  streamChatMessage: mocks.stream,
  regenerateResponse: mocks.regen,
  createConversation: mocks.create,
  listConversations: mocks.list,
  getConversation: mocks.get,
  deleteConversation: mocks.remove,
}));
vi.mock("../src/chat/ChatPage", () => ({
  ChatPage: (props: any) => {
    mocks.page = props;
    return <p>{props.messages.length} messages</p>;
  },
}));
import App from "../src/App";
import { AuthGate } from "../src/auth/AuthGate";
import { ChatComposer } from "../src/chat/ChatComposer";
let root: Root, container: HTMLDivElement;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  mocks.auth.account = { name: "Test" };
  mocks.auth.inProgress = InteractionStatus.None;
  mocks.auth.getAccessToken.mockReset().mockResolvedValue("test-token");
  window.history.replaceState(null, "", "/");
  mocks.rows = [];
  mocks.detail = {};
  mocks.create.mockReset().mockImplementation(async () => {
    const c = {
      id: crypto.randomUUID(),
      title: "New chat",
      created_at: "now",
      updated_at: "now",
    };
    mocks.rows.unshift(c);
    mocks.detail[c.id] = { ...c, messages: [], next_before: null };
    return c;
  });
  mocks.list.mockReset().mockImplementation(async () => [...mocks.rows]);
  mocks.get.mockReset().mockImplementation(async (id) => ({
    ...mocks.detail[id],
    messages: [...mocks.detail[id].messages],
  }));
  mocks.remove.mockReset().mockImplementation(async (id) => {
    mocks.rows = mocks.rows.filter((c) => c.id !== id);
    delete mocks.detail[id];
  });
  mocks.partial = "";
  mocks.send.mockReset().mockResolvedValue("answer");
  async function stream(
    text: string | null,
    token: string,
    id: string,
    event: any,
    signal: AbortSignal,
  ) {
    const messages = mocks.detail[id].messages;
    const user =
      text === null
        ? [...messages].reverse().find((m) => m.role === "user")
        : {
            id: crypto.randomUUID(),
            role: "user",
            content: text,
            status: "pending",
          };
    if (text !== null) messages.push(user);
    const assistant = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      status: "pending",
      reply_to_id: user.id,
    };
    messages.push(assistant);
    event({ type: "start", user, assistant });
    if (mocks.partial) {
      assistant.content = mocks.partial;
      event({ type: "delta", id: assistant.id, text: mocks.partial });
    }
    let abort!: () => void;
    const cancellation = new Promise((_resolve, reject) => {
      abort = () => reject(new DOMException("Stopped", "AbortError"));
      signal.addEventListener("abort", abort, { once: true });
    });
    try {
      const answer: any = await Promise.race([
        mocks.send(user.content, token, id, signal),
        cancellation,
      ]);
      for (const m of messages)
        if (
          m !== assistant &&
          m.role === "assistant" &&
          m.status === "completed"
        )
          m.status = "superseded";
      assistant.content = answer;
      assistant.status = "completed";
      user.status = "completed";
      event({
        type: "delta",
        id: assistant.id,
        text: answer.slice(mocks.partial.length),
      });
      event({ type: "done", assistant });
    } catch (e) {
      assistant.status = signal.aborted ? "cancelled" : "failed";
      if (user.status !== "completed") user.status = assistant.status;
      throw e;
    } finally {
      signal.removeEventListener("abort", abort);
    }
  }
  mocks.stream.mockReset().mockImplementation(stream);
  mocks.regen
    .mockReset()
    .mockImplementation((token, id, event, signal) =>
      stream(null, token, id, event, signal),
    );
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
it("retains chat DOM while acquiring a token", async () => {
  const child = <input defaultValue="retained" />;
  await act(async () => root.render(<AuthGate>{child}</AuthGate>));
  const original = container.querySelector("input");
  mocks.auth.inProgress = InteractionStatus.AcquireToken;
  await act(async () => root.render(<AuthGate>{child}</AuthGate>));
  expect(container.querySelector("input")).toBe(original);
});
it("gates startup without an account", async () => {
  mocks.auth.account = null;
  mocks.auth.inProgress = InteractionStatus.Startup;
  await act(async () =>
    root.render(
      <AuthGate>
        <p>Chat</p>
      </AuthGate>,
    ),
  );
  expect(container.textContent).toContain("Landing");
  expect(container.textContent).not.toContain("Chat");
});
it("guards duplicate sends, blank input, message order and IDs", async () => {
  let finish!: (answer: string) => void;
  const originalSend = mocks.send.getMockImplementation()!;
  mocks.send.mockImplementation(
    (text, token, id) =>
      new Promise((resolve) => {
        finish = async (answer) => {
          await originalSend(text, token, id);
          resolve(answer);
        };
      }),
  );
  await act(async () => root.render(<App />));
  await act(async () => {
    await mocks.page.onSendMessage(" ");
    void mocks.page.onSendMessage("hello");
    await mocks.page.onSendMessage("duplicate");
    mocks.page.onNewConversation();
  });
  expect(mocks.send).toHaveBeenCalledTimes(1);
  expect(mocks.page.messages).toHaveLength(2);
  await act(async () => finish("answer"));
  expect(mocks.page.messages.map((m: any) => m.role)).toEqual([
    "user",
    "assistant",
  ]);
  expect(new Set(mocks.page.messages.map((m: any) => m.id)).size).toBe(2);
});
it("reloads server state after failure and permits an explicit new attempt", async () => {
  mocks.send.mockRejectedValueOnce(new Error("temporarily unavailable"));
  await act(async () => root.render(<App />));
  await act(async () => {
    expect(await mocks.page.onSendMessage("hello")).toBe(false);
  });
  expect(mocks.page.error).toContain("unavailable");
  await act(async () => {
    mocks.page.onRegenerate();
  });
  expect(mocks.page.error).toBeNull();
  expect(mocks.page.messages).toHaveLength(3);
  expect(
    mocks.page.messages.filter((m: any) => m.role === "user"),
  ).toHaveLength(1);
});
it("avoids HTTP after unmount during token acquisition", async () => {
  let finish!: (token: string) => void, request!: Promise<boolean>;
  await act(async () => root.render(<App />));
  mocks.auth.getAccessToken.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await act(async () => {
    request = mocks.page.onSendMessage("hello");
  });
  await act(async () => root.unmount());
  finish("test-token");
  await request;
  expect(mocks.send).not.toHaveBeenCalled();
});
it("does not submit Enter during IME composition", async () => {
  const submit = vi.fn();
  await act(async () =>
    root.render(
      <ChatComposer
        input="hello"
        isLoading={false}
        onChange={() => {}}
        onSubmit={submit}
      />,
    ),
  );
  const textarea = container.querySelector("textarea")!;
  await act(async () =>
    textarea.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        isComposing: true,
        bubbles: true,
      }),
    ),
  );
  expect(submit).not.toHaveBeenCalled();
  await act(async () =>
    textarea.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    ),
  );
  expect(submit).toHaveBeenCalledOnce();
});
it("resets the chat subtree when the authenticated account changes", async () => {
  mocks.auth.account = { name: "First", homeAccountId: "first" };
  const child = <input defaultValue="first-account-draft" />;
  await act(async () => root.render(<AuthGate>{child}</AuthGate>));
  const original = container.querySelector("input");
  mocks.auth.account = { name: "Second", homeAccountId: "second" };
  await act(async () => root.render(<AuthGate>{child}</AuthGate>));
  expect(container.querySelector("input")).not.toBe(original);
});
it("gates startup even when a cached account exists", async () => {
  mocks.auth.inProgress = InteractionStatus.Startup;
  await act(async () =>
    root.render(
      <AuthGate>
        <p>Chat</p>
      </AuthGate>,
    ),
  );
  expect(container.textContent).toContain("Landing");
  expect(container.textContent).not.toContain("Chat");
});

it("keeps landing mounted with a disabled sign-in during MSAL startup", async () => {
  mocks.auth.account = null;
  mocks.auth.inProgress = InteractionStatus.Startup;
  await act(async () =>
    root.render(
      <AuthGate>
        <p>Chat</p>
      </AuthGate>,
    ),
  );
  expect(mocks.landing.isBusy).toBe(true);
  expect(mocks.landing.authStatus).toBe("Preparing Microsoft sign-in…");
  mocks.auth.inProgress = InteractionStatus.None;
  await act(async () =>
    root.render(
      <AuthGate>
        <p>Chat</p>
      </AuthGate>,
    ),
  );
  expect(mocks.landing.isBusy).toBe(false);
  expect(mocks.landing.authStatus).toBeNull();
});

it("creates a persisted chat, reopens it after reload and deletes it through the API", async () => {
  await act(async () => root.render(<App />));
  await act(async () => mocks.page.onNewConversation());
  const id = mocks.page.currentConversationId;
  expect(mocks.create).toHaveBeenCalledOnce();
  expect(mocks.page.conversations[0].id).toBe(id);
  await act(async () => {
    await mocks.page.onSendMessage("remember blue");
  });
  await act(async () => root.unmount());
  root = createRoot(container);
  await act(async () => root.render(<App />));
  expect(mocks.page.currentConversationId).toBe(id);
  expect(mocks.page.messages.map((m: any) => m.text)).toEqual([
    "remember blue",
    "answer",
  ]);
  await act(async () => mocks.page.onDeleteConversation(id));
  expect(mocks.remove).toHaveBeenCalledWith(
    id,
    "test-token",
    expect.any(AbortSignal),
  );
  expect(mocks.page.messages).toEqual([]);
  expect(mocks.page.conversations).toEqual([]);
});

it("restores the selected older conversation and ignores token callback changes during a send", async () => {
  const older = await mocks.create(),
    newer = await mocks.create();
  await act(async () => root.render(<App />));
  expect(mocks.page.currentConversationId).toBe(newer.id);
  await act(async () => mocks.page.onSelectConversation(older.id));
  expect(mocks.page.currentConversationId).toBe(older.id);
  await act(async () => root.unmount());
  root = createRoot(container);
  await act(async () => root.render(<App />));
  expect(mocks.page.currentConversationId).toBe(older.id);
  const initialLists = mocks.list.mock.calls.length;
  mocks.auth.getAccessToken = vi.fn().mockResolvedValue("renewed-token");
  await act(async () => root.render(<App />));
  expect(mocks.list.mock.calls.length).toBe(initialLists);
  await act(async () => {
    await mocks.page.onSendMessage("continue");
  });
  expect(mocks.send).toHaveBeenLastCalledWith(
    "continue",
    "renewed-token",
    older.id,
    expect.any(AbortSignal),
  );
});

it("shows an already persisted failed prompt after an upstream error", async () => {
  mocks.send.mockRejectedValueOnce(new Error("temporarily unavailable"));
  await act(async () => root.render(<App />));
  await act(async () => {
    expect(await mocks.page.onSendMessage("hello")).toBe(false);
  });
  expect(mocks.page.messages[0]).toMatchObject({
    status: "failed",
    text: "hello",
  });
  expect(mocks.page.error).toContain("unavailable");
});

it("renders deltas before completion, stops without an error, then sends again", async () => {
  mocks.partial = "Part";
  mocks.send.mockImplementationOnce(() => new Promise(() => {}));
  await act(async () => root.render(<App />));
  let request!: Promise<boolean>;
  await act(async () => {
    request = mocks.page.onSendMessage("hello");
  });
  expect(mocks.page.isGenerating).toBe(true);
  expect(mocks.page.messages[1].text).toBe("Part");
  await act(async () => {
    mocks.page.onStopGeneration();
    await request;
  });
  expect(mocks.page.isGenerating).toBe(false);
  expect(mocks.page.error).toBeNull();
  expect(mocks.page.notice).toContain("stopped");
  expect(mocks.page.messages[1].status).toBe("cancelled");
  mocks.partial = "";
  await act(async () => {
    expect(await mocks.page.onSendMessage("continue")).toBe(true);
  });
  expect(mocks.page.messages[3].status).toBe("completed");
});

it("regenerates the same prompt and can stop that attempt while keeping the old response", async () => {
  await act(async () => root.render(<App />));
  await act(async () => {
    await mocks.page.onSendMessage("hello");
  });
  mocks.send.mockImplementationOnce(() => new Promise(() => {}));
  mocks.partial = "Part";
  await act(async () => mocks.page.onRegenerate());
  expect(mocks.page.messages.map((m: any) => m.role)).toEqual([
    "user",
    "assistant",
    "assistant",
  ]);
  expect(mocks.page.messages[0].text).toBe("hello");
  expect(mocks.page.isGenerating).toBe(true);
  await act(async () => mocks.page.onStopGeneration());
  expect(mocks.page.messages.map((m: any) => m.status)).toEqual([
    "completed",
    "completed",
    "cancelled",
  ]);
  expect(
    mocks.page.messages.filter((m: any) => m.role === "user"),
  ).toHaveLength(1);
});

it("an explicit resend of the failed latest prompt regenerates without another user row", async () => {
  mocks.send.mockRejectedValueOnce(new Error("temporarily unavailable"));
  await act(async () => root.render(<App />));
  await act(async () => {
    expect(await mocks.page.onSendMessage("hello")).toBe(false);
  });
  await act(async () => {
    expect(await mocks.page.onSendMessage("hello")).toBe(true);
  });
  expect(mocks.regen).toHaveBeenCalledOnce();
  expect(
    mocks.page.messages.filter((m: any) => m.role === "user"),
  ).toHaveLength(1);
  expect(mocks.page.messages.map((m: any) => m.status)).toEqual([
    "completed",
    "failed",
    "completed",
  ]);
});
