import { afterEach, describe, expect, it, vi } from "vitest";

import { sendChatMessage } from "../src/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("sendChatMessage", () => {
  it("reuses one conversation ID for consecutive messages", async () => {
    const conversationId = "550e8400-e29b-41d4-a716-446655440000";
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => ({
        ok: true,
        json: async () => ({ message: "ok" }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await sendChatMessage("first", "access-token", conversationId);
    await sendChatMessage("second", "access-token", conversationId);

    for (const [, options] of fetchMock.mock.calls) {
      expect(options?.method).toBe("POST");
      expect(options?.headers).toEqual({
        Authorization: "Bearer access-token",
        "Content-Type": "application/json",
      });
    }

    const requestBodies = fetchMock.mock.calls.map(([, options]) =>
      JSON.parse(String(options?.body)),
    );
    expect(requestBodies).toEqual([
      { message: "first", conversation_id: conversationId },
      { message: "second", conversation_id: conversationId },
    ]);
  });
});

it.each([null, [], {}, { message: null }, { message: " " }, { message: 12 }])(
  "rejects malformed success payload %j",
  async (body) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => body })),
    );
    await expect(sendChatMessage("hello", "token", "chat")).rejects.toThrow(
      "invalid response",
    );
  },
);

it.each([401, 403, 422, 429, 502, 503, 504, 500])(
  "safely handles HTTP %s",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status,
        json: async () => ({ detail: "private secret" }),
      })),
    );
    try {
      await sendChatMessage("hello", "token", "chat");
      throw new Error("expected failure");
    } catch (error) {
      expect(String(error)).not.toContain("private secret");
      expect(String(error)).not.toContain("expected failure");
    }
  },
);

it("rejects empty tokens without issuing a request", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  await expect(sendChatMessage("hello", " ", "chat")).rejects.toThrow(
    "Sign in",
  );
  expect(fetch).not.toHaveBeenCalled();
});

it("handles network failure without displaying transport diagnostics", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new Error("private URL");
    }),
  );
  await expect(sendChatMessage("hello", "token", "chat")).rejects.toThrow(
    "Check your connection",
  );
});

it("cancels an in-flight request", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options.signal.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    ),
  );
  const controller = new AbortController();
  const request = sendChatMessage("hello", "token", "chat", controller.signal);
  controller.abort();
  await expect(request).rejects.toMatchObject({ name: "AbortError" });
});

it("bounds the request deadline", async () => {
  vi.useFakeTimers();
  try {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, options) =>
          new Promise((_resolve, reject) => {
            options.signal.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      ),
    );
    const assertion = expect(
      sendChatMessage("hello", "token", "chat"),
    ).rejects.toThrow("timed out");
    await vi.advanceTimersByTimeAsync(40_000);
    await assertion;
  } finally {
    vi.useRealTimers();
  }
});
it("rejects non-JSON success responses", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => {
        throw new SyntaxError("private payload");
      },
    })),
  );
  await expect(sendChatMessage("hello", "token", "chat")).rejects.toThrow(
    "invalid response",
  );
});
it("does not issue HTTP for an already cancelled request", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const controller = new AbortController();
  controller.abort();
  await expect(
    sendChatMessage("hello", "token", "chat", controller.signal),
  ).rejects.toMatchObject({ name: "AbortError" });
  expect(fetch).not.toHaveBeenCalled();
});

it("uses bearer authentication for conversation CRUD and encodes identifiers", async () => {
  const {
    createConversation,
    listConversations,
    getConversation,
    deleteConversation,
  } = await import("../src/api");
  const fetch = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({}),
  }));
  vi.stubGlobal("fetch", fetch);
  await createConversation("test-token");
  await listConversations("test-token", 50);
  await getConversation("chat/id", "test-token", 100);
  await deleteConversation("chat/id", "test-token");
  expect(fetch.mock.calls.map((c: any) => c[1].method)).toEqual([
    "POST",
    "GET",
    "GET",
    "DELETE",
  ]);
  expect((fetch.mock.calls as any)[2][0]).toContain("chat%2Fid?before=100");
  for (const call of fetch.mock.calls as any[])
    expect(call[1].headers).toEqual({ Authorization: "Bearer test-token" });
});
