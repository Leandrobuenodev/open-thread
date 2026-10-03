// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { ChatSidebar } from "../src/chat/ChatSidebar";
import { ChatProjectDialog } from "../src/chat/ChatProjectDialog";
import { ChatSearch } from "../src/chat/ChatSearch";
import { ChatMessage } from "../src/chat/ChatMessage";

let root: Root, container: HTMLDivElement;
const select = vi.fn(),
  signOut = vi.fn();
const props = {
  authError: null,
  isCollapsed: false,
  isNewConversationDisabled: false,
  isSigningOut: false,
  onNewConversation: vi.fn(),
  onSignOut: signOut,
  onToggleCollapse: vi.fn(),
  onSelectMessage: select,
  userName: "Session User",
  onOpenSearch: vi.fn(),
};
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.clearAllMocks();
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: false })),
  );
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
it("shows honest empty categories without placeholder conversations", async () => {
  await act(async () => root.render(<ChatSidebar {...props} messages={[]} />));
  expect(container.textContent).not.toContain("No pinned chats.");
  expect(container.querySelector('[aria-controls="chat-pinned"]')).toBeNull();
  expect(container.textContent).not.toContain("This session only.");
  expect(container.textContent).toContain("No saved conversations yet.");
  const projects = container.querySelector<HTMLButtonElement>(
    '[aria-controls="chat-projects"]',
  )!;
  await act(async () => projects.click());
  expect(projects.getAttribute("aria-expanded")).toBe("true");
  expect(container.textContent).toContain("No projects yet.");
});
it("searches real session messages and selects their existing IDs", async () => {
  await act(async () =>
    root.render(
      <ChatSearch
        onClose={vi.fn()}
        onSelectMessage={select}
        messages={[
          { id: "prompt", role: "user", text: "Where is the boundary?" },
          { id: "reply", role: "assistant", text: "At the API boundary." },
        ]}
      />,
    ),
  );
  const input = document.querySelector("input")!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, "api");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(document.body.textContent).toContain("1 matching messages");
  await act(async () =>
    document.querySelector<HTMLButtonElement>(".chat-search__result")!.click(),
  );
  expect(select).toHaveBeenCalledWith("reply");
});
it("keeps new chat, search and account actions accessible in the collapsed rail", async () => {
  await act(async () =>
    root.render(<ChatSidebar {...props} isCollapsed messages={[]} />),
  );
  for (const label of [
    "Expand sidebar",
    "New chat",
    "Search this conversation",
    "Account: Session User",
  ]) {
    expect(container.querySelector(`[aria-label="${label}"]`)).not.toBeNull();
  }
  expect(container.querySelector(".chat-sidebar__library")).toBeNull();
});
it("keeps the actual sign-out callback behind the account disclosure", async () => {
  await act(async () => root.render(<ChatSidebar {...props} messages={[]} />));
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-label="Account: Session User"]')!
      .click(),
  );
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>(".chat-sidebar__signout")!
      .click(),
  );
  expect(signOut).toHaveBeenCalledOnce();
});
it("renders code and potential HTML as literal text without executable markup", async () => {
  await act(async () =>
    root.render(
      <ChatMessage
        message={{
          id: "safe",
          role: "assistant",
          text: "Text\n```html\n<img src=x onerror=alert(1)>\n```",
        }}
      />,
    ),
  );
  expect(container.querySelector("code")?.textContent).toContain("<img");
  expect(container.querySelector("img")).toBeNull();
});

it("search opens from the collapsed rail without expanding it", async () => {
  await act(async () =>
    root.render(<ChatSidebar {...props} isCollapsed messages={[]} />),
  );
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>(
        '[aria-label="Search this conversation"]',
      )!
      .click(),
  );
  expect(props.onOpenSearch).toHaveBeenCalledOnce();
  expect(props.onToggleCollapse).not.toHaveBeenCalled();
});
it("search supports recent session chat, keyboard results, Escape and outside close", async () => {
  const close = vi.fn();
  await act(async () =>
    root.render(
      <ChatSearch
        messages={[{ id: "real", role: "user", text: "Real session" }]}
        onClose={close}
        onSelectMessage={select}
      />,
    ),
  );
  expect(document.body.textContent).toContain("Recent chats");
  expect(document.activeElement).toBe(document.querySelector("input"));
  await act(async () =>
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }),
    ),
  );
  expect(document.activeElement).toBe(
    document.querySelector(".chat-search__result"),
  );
  await act(async () =>
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    ),
  );
  expect(close).toHaveBeenCalledOnce();
  await act(async () =>
    document.querySelector<HTMLDivElement>(".chat-search")!.click(),
  );
  expect(close).toHaveBeenCalledTimes(2);
});

it("renders populated pins and real project children as inline disclosures", async () => {
  await act(async () =>
    root.render(
      <ChatSidebar
        {...props}
        messages={[]}
        pinnedChats={[
          {
            id: "pin",
            title: "Pinned session chat",
            messageId: "real-message",
          },
        ]}
        projects={[
          {
            id: "project",
            name: "Session project",
            chats: [
              { id: "chat", title: "Project chat", messageId: "real-message" },
            ],
          },
        ]}
      />,
    ),
  );
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-controls="chat-pinned"]')!
      .click(),
  );
  expect(container.textContent).toContain("Pinned session chat");
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-controls="project-project"]')!
      .click(),
  );
  const chat = Array.from(container.querySelectorAll("button")).find(
    (button) => button.textContent === "Project chat",
  )!;
  await act(async () => chat.click());
  expect(select).toHaveBeenCalledWith("real-message");
});
it("validates and trims a session project name without double submission", async () => {
  HTMLDialogElement.prototype.showModal = vi.fn();
  const create = vi.fn(),
    close = vi.fn();
  await act(async () =>
    root.render(<ChatProjectDialog onCreate={create} onClose={close} />),
  );
  const form = document.querySelector("form")!;
  await act(async () =>
    form.dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true }),
    ),
  );
  expect(create).not.toHaveBeenCalled();
  const input = document.querySelector("input")!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, "  My project  ");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => {
    form.dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true }),
    );
    form.dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true }),
    );
  });
  expect(create).toHaveBeenCalledExactlyOnceWith("My project");
  await act(async () =>
    document
      .querySelector("dialog")!
      .dispatchEvent(new Event("cancel", { cancelable: true })),
  );
  expect(close).toHaveBeenCalledOnce();
});

it("lists API conversations, selects their IDs and confirms deletion", async () => {
  const choose = vi.fn(),
    remove = vi.fn();
  vi.spyOn(window, "confirm").mockReturnValue(true);
  await act(async () =>
    root.render(
      <ChatSidebar
        {...props}
        messages={[]}
        conversations={[
          {
            id: "conversation-id",
            title: "Saved title",
            created_at: "now",
            updated_at: "now",
          },
        ]}
        currentConversationId="conversation-id"
        onSelectConversation={choose}
        onDeleteConversation={remove}
      />,
    ),
  );
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-current="page"]')!
      .click(),
  );
  expect(choose).toHaveBeenCalledWith("conversation-id");
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>(
        '[aria-label="Delete conversation: Saved title"]',
      )!
      .click(),
  );
  expect(remove).toHaveBeenCalledWith("conversation-id");
  vi.restoreAllMocks();
});
