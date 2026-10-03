import { afterEach, expect, it, vi } from "vitest";
import { regenerateResponse, streamChatMessage } from "../src/api";

const user = { id: "u", role: "user", content: "hi", status: "pending" };
const assistant = {
  id: "a",
  role: "assistant",
  content: "",
  status: "pending",
};
const frame = (event: string, data: unknown) =>
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
function response(parts: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const part of parts) controller.enqueue(encoder.encode(part));
        controller.close();
      },
    }),
    { headers: { "content-type": "text/event-stream" } },
  );
}
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
it("parses split SSE frames and UTF-8 chunks in order, sending an authenticated streaming POST", async () => {
  const content =
    frame("start", { user, assistant }) +
    frame("delta", { id: "a", text: "Olá" }) +
    frame("delta", { id: "a", text: " world" }) +
    frame("done", {
      assistant: { ...assistant, status: "completed", content: "Olá world" },
    });
  const bytes = new TextEncoder().encode(content);
  const fetch = vi.fn(
    async () =>
      new Response(
        new ReadableStream({
          start(controller) {
            for (const byte of bytes)
              controller.enqueue(new Uint8Array([byte]));
            controller.close();
          },
        }),
        { headers: { "content-type": "text/event-stream" } },
      ),
  );
  vi.stubGlobal("fetch", fetch);
  const events: any[] = [];
  await streamChatMessage("hi", "fake-token", "c", (event) =>
    events.push(event),
  );
  expect(events.map((e) => e.type)).toEqual([
    "start",
    "delta",
    "delta",
    "done",
  ]);
  expect(events[1].text).toBe("Olá");
  const options = (fetch.mock.calls as any)[0][1];
  expect(options.headers.Authorization).toBe("Bearer fake-token");
  expect(JSON.parse(options.body)).toEqual({
    message: "hi",
    conversation_id: "c",
    stream: true,
  });
});
it("regenerate uses its endpoint without resending the user prompt", async () => {
  const fetch = vi.fn(async () =>
    response([
      frame("start", { user, assistant }),
      frame("done", {
        assistant: { ...assistant, status: "completed", content: "new" },
      }),
    ]),
  );
  vi.stubGlobal("fetch", fetch);
  await regenerateResponse("token", "c", () => {});
  expect((fetch.mock.calls as any)[0][0]).toContain(
    "/conversations/c/regenerate",
  );
  expect((fetch.mock.calls as any)[0][1].body).toBeUndefined();
});
it.each([401, 403, 429])(
  "distinguishes HTTP %s and hides backend bodies",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("secret", { status })),
    );
    await expect(
      streamChatMessage("hi", "token", "c", () => {}),
    ).rejects.toMatchObject({
      status,
      code: status === 429 ? "rate_limit" : "auth",
    });
  },
);
it.each(["timeout", "upstream", "rate_limit"])(
  "handles an SSE %s error after a partial delta",
  async (code) => {
    const seen: any[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        response([
          frame("start", { user, assistant }),
          frame("delta", { id: "a", text: "partial" }),
          frame("error", {
            code,
            status:
              code === "timeout" ? 504 : code === "rate_limit" ? 429 : 502,
            detail: "secret",
          }),
        ]),
      ),
    );
    await expect(
      streamChatMessage("hi", "token", "c", (e) => seen.push(e)),
    ).rejects.toMatchObject({ code });
    expect(seen.at(-1).text).toBe("partial");
  },
);
it("reports abrupt EOF as interruption rather than a completed response", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      response([
        frame("start", { user, assistant }),
        frame("delta", { id: "a", text: "partial" }),
      ]),
    ),
  );
  await expect(
    streamChatMessage("hi", "token", "c", () => {}),
  ).rejects.toMatchObject({ code: "network" });
});
it("cancels a live stream and separates Stop from timeout", async () => {
  const controller = new AbortController();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (_url, options) =>
        new Response(
          new ReadableStream({
            start(stream) {
              options.signal.addEventListener("abort", () =>
                stream.error(new DOMException("Aborted", "AbortError")),
              );
            },
          }),
          { headers: { "content-type": "text/event-stream" } },
        ),
    ),
  );
  const request = streamChatMessage(
    "hi",
    "token",
    "c",
    () => {},
    controller.signal,
  );
  const assertion = expect(request).rejects.toMatchObject({
    name: "AbortError",
  });
  await Promise.resolve();
  controller.abort();
  await assertion;
});
it("bounds the entire streaming deadline", async () => {
  vi.useFakeTimers();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (_url, options) =>
        new Response(
          new ReadableStream({
            start(stream) {
              options.signal.addEventListener("abort", () =>
                stream.error(new DOMException("Aborted", "AbortError")),
              );
            },
          }),
          { headers: { "content-type": "text/event-stream" } },
        ),
    ),
  );
  const assertion = expect(
    streamChatMessage("hi", "token", "c", () => {}),
  ).rejects.toMatchObject({ code: "timeout" });
  await vi.advanceTimersByTimeAsync(40000);
  await assertion;
});
