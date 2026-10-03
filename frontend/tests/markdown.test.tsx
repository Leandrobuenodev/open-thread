// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { ChatMessage } from "../src/chat/ChatMessage";
import { ChatComposer } from "../src/chat/ChatComposer";

let root: Root, container: HTMLDivElement;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.restoreAllMocks();
  vi.useRealTimers();
});
async function markdown(text: string) {
  await act(async () =>
    root.render(
      <ChatMessage
        message={{ id: "a", role: "assistant", text, status: "completed" }}
      />,
    ),
  );
}
it("renders rich Markdown and GFM tables while leaving user messages plain", async () => {
  await markdown(
    "# Heading\n\nA **bold** and *italic* paragraph with `inline`.\n\n- One\n- Two\n\n1. First\n2. Second\n\n> Quote\n\n[Link](https://example.com)\n\n| A | B |\n|---|---|\n| 1 | 2 |",
  );
  expect(container.querySelector("h1")?.textContent).toBe("Heading");
  expect(container.querySelector("strong")?.textContent).toBe("bold");
  expect(container.querySelector("em")?.textContent).toBe("italic");
  expect(container.querySelectorAll("li")).toHaveLength(4);
  expect(container.querySelector("blockquote")?.textContent).toContain("Quote");
  expect(container.querySelector("a")?.getAttribute("href")).toBe(
    "https://example.com",
  );
  expect(container.querySelector("a")?.getAttribute("rel")).toBe(
    "noopener noreferrer",
  );
  expect(container.querySelector("code")?.textContent).toBe("inline");
  expect(container.querySelector("table")?.textContent).toContain("AB12");
  await act(async () =>
    root.render(
      <ChatMessage
        message={{ id: "u", role: "user", text: "# Plain **text**" }}
      />,
    ),
  );
  expect(container.querySelector("h1")).toBeNull();
  expect(container.textContent).toContain("# Plain **text**");
});
it("never executes raw HTML, javascript URLs, or remote images", async () => {
  await markdown(
    '<script>alert(1)</script>\n\n<img src="x" onerror="alert(1)">\n\n[bad](javascript:alert%281%29)\n\n![tracking](https://example.com/pixel)',
  );
  expect(container.querySelector("script,img")).toBeNull();
  expect(container.querySelector("a")?.getAttribute("href")).not.toContain(
    "javascript:",
  );
});
it("highlights only selected languages, copies exact code and shows brief feedback", async () => {
  const copy = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: copy },
  });
  await markdown('```python\nprint("hello")\n```');
  expect(
    container.querySelector(".chat-message__code-toolbar")?.textContent,
  ).toContain("python");
  expect(container.querySelector("pre code")?.className).toBe(
    "language-python",
  );
  expect(
    container.querySelector("pre code span[class*='hljs']"),
  ).not.toBeNull();
  expect(container.querySelector("pre")?.tabIndex).toBe(0);
  vi.useFakeTimers();
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-label="Copy code"]')!
      .click(),
  );
  expect(copy).toHaveBeenCalledWith('print("hello")');
  expect(
    container.querySelector('[aria-label="Copy code"]')?.textContent,
  ).toContain("Copied");
  await act(async () => vi.advanceTimersByTime(1800));
  expect(
    container.querySelector('[aria-label="Copy code"]')?.textContent,
  ).not.toContain("Copied");
});
it("renders unknown and incomplete fences safely and copies the whole response", async () => {
  const copy = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: copy },
  });
  const text = "```unknown\n<img src=x onerror=alert(1)>";
  await markdown(text);
  expect(container.querySelector("pre code")?.textContent).toContain("<img");
  expect(container.querySelector("img")).toBeNull();
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-label="Copy response"]')!
      .click(),
  );
  expect(copy).toHaveBeenCalledWith(text);
});
it("shows Stop only during generation and normal Send after cancellation", async () => {
  const stop = vi.fn(),
    submit = vi.fn();
  await act(async () =>
    root.render(
      <ChatComposer
        input=""
        isLoading
        isGenerating
        onStop={stop}
        onChange={() => {}}
        onSubmit={submit}
      />,
    ),
  );
  const button = container.querySelector<HTMLButtonElement>(
    '[aria-label="Stop generation"]',
  )!;
  expect(button.disabled).toBe(false);
  await act(async () => button.click());
  expect(stop).toHaveBeenCalledOnce();
  expect(submit).not.toHaveBeenCalled();
  await act(async () =>
    root.render(
      <ChatComposer
        input="next"
        isLoading={false}
        onChange={() => {}}
        onSubmit={submit}
      />,
    ),
  );
  expect(container.querySelector('[aria-label="Stop generation"]')).toBeNull();
  expect(
    container.querySelector<HTMLButtonElement>('[aria-label="Send message"]')
      ?.disabled,
  ).toBe(false);
});
it("offers regenerate on terminal attempts but not while generating", async () => {
  const regenerate = vi.fn();
  await act(async () =>
    root.render(
      <ChatMessage
        message={{
          id: "a",
          role: "assistant",
          text: "partial",
          status: "cancelled",
        }}
        onRegenerate={regenerate}
      />,
    ),
  );
  await act(async () =>
    Array.from(container.querySelectorAll("button"))
      .find((b) => b.textContent === "Regenerate")!
      .click(),
  );
  expect(regenerate).toHaveBeenCalledOnce();
  await act(async () =>
    root.render(
      <ChatMessage
        message={{
          id: "a",
          role: "assistant",
          text: "part",
          status: "pending",
          streaming: true,
        }}
        onRegenerate={regenerate}
      />,
    ),
  );
  expect(
    container.querySelector('[aria-label="Generating response"]'),
  ).not.toBeNull();
  expect(container.textContent).not.toContain("Regenerate");
});
