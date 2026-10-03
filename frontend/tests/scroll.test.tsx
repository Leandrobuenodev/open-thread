// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
vi.mock("../src/auth/AuthProvider", () => ({
  useEntraAuth: () => ({
    account: { name: "Local test" },
    authError: null,
    signOut: vi.fn(),
  }),
}));
import { ChatPage } from "../src/chat/ChatPage";
let root: Root, container: HTMLDivElement;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});
it("follows streamed text only near the bottom, preserves reading position and anchors older pages", async () => {
  const older = vi.fn();
  const base = {
    error: null,
    isLoading: false,
    onSendMessage: vi.fn(),
    onNewConversation: vi.fn(),
    currentConversationId: "c",
    onLoadOlder: older,
  };
  const message = {
    id: "a",
    role: "assistant" as const,
    text: "first",
    status: "pending" as const,
    streaming: true,
  };
  await act(async () =>
    root.render(<ChatPage {...base} messages={[message]} />),
  );
  const scroll = container.querySelector<HTMLDivElement>(".chat-conversation")!;
  let height = 1000;
  Object.defineProperty(scroll, "scrollHeight", { get: () => height });
  Object.defineProperty(scroll, "clientHeight", { get: () => 100 });
  scroll.scrollTop = 900;
  await act(async () =>
    scroll.dispatchEvent(new Event("scroll", { bubbles: true })),
  );
  height = 1100;
  await act(async () =>
    root.render(
      <ChatPage {...base} messages={[{ ...message, text: "first chunk" }]} />,
    ),
  );
  expect(scroll.scrollTop).toBe(1100);
  scroll.scrollTop = 200;
  await act(async () =>
    scroll.dispatchEvent(new Event("scroll", { bubbles: true })),
  );
  height = 1200;
  await act(async () =>
    root.render(
      <ChatPage
        {...base}
        messages={[{ ...message, text: "first chunk next" }]}
      />,
    ),
  );
  expect(scroll.scrollTop).toBe(200);
  const load = Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent === "Load older messages",
  )!;
  await act(async () => load.click());
  expect(older).toHaveBeenCalledOnce();
  height = 1400;
  await act(async () =>
    root.render(
      <ChatPage
        {...base}
        messages={[{ ...message, id: "old", text: "older" }, message]}
      />,
    ),
  );
  expect(scroll.scrollTop).toBe(400);
});
