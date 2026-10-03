const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
)
  .trim()
  .replace(/\/+$/, "");
export const CHAT_TIMEOUT_MS = 40_000;

function statusMessage(status: number): string {
  if (status === 401)
    return "Your session could not be authorized. Sign out and sign in again.";
  if (status === 403)
    return "Your account does not have permission to use this API.";
  if (status === 422)
    return "The message could not be accepted. Check it and try again.";
  if (status === 429)
    return "Too many requests. Please wait before trying again.";
  if (status === 502 || status === 503 || status === 504)
    return "The assistant is temporarily unavailable. Please try again later.";
  return "The assistant request failed. Please try again.";
}

export async function sendChatMessage(
  message: string,
  accessToken: string,
  conversationId: string,
  signal?: AbortSignal,
): Promise<string> {
  if (!accessToken.trim()) throw new Error("Sign in before sending a message.");
  if (!API_BASE_URL)
    throw new Error("The application API URL is not configured.");
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener("abort", cancel, { once: true });
  if (signal?.aborted) cancel();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, CHAT_TIMEOUT_MS);
  try {
    let response: Response;
    try {
      if (controller.signal.aborted)
        throw new DOMException("Request cancelled.", "AbortError");
      response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message, conversation_id: conversationId }),
        signal: controller.signal,
      });
    } catch {
      if (controller.signal.aborted) throw new Error("Request cancelled.");
      throw new Error(
        "Unable to reach the API. Check your connection and try again.",
      );
    }
    if (!response.ok) throw new Error(statusMessage(response.status));
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new Error("The API returned an invalid response.");
    }
    if (
      body === null ||
      typeof body !== "object" ||
      !("message" in body) ||
      typeof body.message !== "string" ||
      !body.message.trim()
    ) {
      throw new Error("The API returned an invalid response.");
    }
    return body.message;
  } catch (error) {
    if (timedOut)
      throw new Error("The request timed out. Please try again later.");
    if (signal?.aborted)
      throw new DOMException("Request cancelled.", "AbortError");
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
  }
}

export type Conversation = {
  id: string;
  title: string;
  project_id?: string | null;
  is_pinned?: boolean;
  created_at: string;
  updated_at: string;
};
export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sequence: number;
  status: "pending" | "completed" | "failed" | "cancelled" | "superseded";
  reply_to_id?: string | null;
  replaces_id?: string | null;
  attachments?: Attachment[];
};
export type ConversationDetail = Conversation & {
  messages: StoredMessage[];
  next_before: number | null;
};

async function conversationRequest<T>(
  path: string,
  token: string,
  method = "GET",
  signal?: AbortSignal,
): Promise<T> {
  if (!token.trim()) throw new Error("Sign in to access conversations.");
  if (!API_BASE_URL)
    throw new Error("The application API URL is not configured.");
  if (signal?.aborted)
    throw new DOMException("Request cancelled.", "AbortError");
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener("abort", cancel, { once: true });
  const timer = setTimeout(cancel, CHAT_TIMEOUT_MS);
  try {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/api/conversations${path}`, {
        method,
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
    } catch {
      throw new Error(
        "Unable to reach conversation storage. Reopen the conversation before sending again.",
      );
    }
    if (!response.ok)
      throw new Error(
        response.status === 404
          ? "Conversation not found."
          : response.status === 409
            ? "Conversation is processing a message."
            : statusMessage(response.status),
      );
    if (response.status === 204) return undefined as T;
    try {
      return (await response.json()) as T;
    } catch {
      throw new Error("Conversation storage returned an invalid response.");
    }
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
  }
}
export const listConversations = (
  token: string,
  offset = 0,
  signal?: AbortSignal,
) =>
  conversationRequest<Conversation[]>(
    `?offset=${offset}`,
    token,
    "GET",
    signal,
  );
export const createConversation = (token: string, signal?: AbortSignal) =>
  conversationRequest<Conversation>("", token, "POST", signal);
export const getConversation = (
  id: string,
  token: string,
  before?: number,
  signal?: AbortSignal,
) =>
  conversationRequest<ConversationDetail>(
    `/${encodeURIComponent(id)}${before ? `?before=${before}` : ""}`,
    token,
    "GET",
    signal,
  );
export const deleteConversation = (
  id: string,
  token: string,
  signal?: AbortSignal,
) =>
  conversationRequest<void>(
    `/${encodeURIComponent(id)}`,
    token,
    "DELETE",
    signal,
  );

export type StreamEvent =
  | { type: "start"; user: StoredMessage; assistant: StoredMessage }
  | { type: "delta"; id: string; text: string }
  | { type: "done"; assistant: StoredMessage };
export class ChatStreamError extends Error {
  constructor(
    public code: string,
    message: string,
    public status?: number,
    public retryAfter?: number,
  ) {
    super(message);
  }
}

function validStoredMessage(value: any): value is StoredMessage {
  return (
    value &&
    typeof value.id === "string" &&
    value.id.length > 0 &&
    typeof value.content === "string" &&
    (value.role === "user" || value.role === "assistant") &&
    ["pending", "completed", "failed", "cancelled", "superseded"].includes(
      value.status,
    )
  );
}

async function streamConversation(
  message: string | null,
  token: string,
  id: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
  attachmentIds: string[] = [],
  editId?: string,
): Promise<void> {
  if (!token.trim())
    throw new ChatStreamError("auth", "Sign in before sending a message.", 401);
  if (!API_BASE_URL)
    throw new ChatStreamError(
      "configuration",
      "The application API URL is not configured.",
    );
  if (signal?.aborted)
    throw new DOMException("Request cancelled.", "AbortError");
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener("abort", cancel, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    cancel();
  }, CHAT_TIMEOUT_MS);
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    const path = editId
      ? `/api/conversations/${encodeURIComponent(id)}/messages/${encodeURIComponent(editId)}/edit`
      : message === null
        ? `/api/conversations/${encodeURIComponent(id)}/regenerate`
        : "/api/chat";
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body:
        message === null
          ? undefined
          : JSON.stringify(
              editId
                ? { message }
                : {
                    message,
                    conversation_id: id,
                    stream: true,
                    ...(attachmentIds.length
                      ? { attachment_ids: attachmentIds }
                      : {}),
                  },
            ),
    });
    if (!response.ok)
      throw new ChatStreamError(
        response.status === 401 || response.status === 403
          ? "auth"
          : response.status === 429
            ? "rate_limit"
            : "http",
        response.status === 409
          ? "Conversation is processing a message."
          : statusMessage(response.status),
        response.status,
      );
    if (
      !response.body ||
      !response.headers.get("content-type")?.includes("text/event-stream")
    )
      throw new ChatStreamError(
        "protocol",
        "The API returned an invalid stream.",
      );
    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let started = false;
    let assistantId = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      if (buffer.length > 262144)
        throw new ChatStreamError(
          "protocol",
          "The API stream exceeded its safety limit.",
        );
      let boundary: RegExpExecArray | null;
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary[0].length);
        const lines = frame.split(/\r?\n/);
        const type = lines
          .find((l) => l.startsWith("event:"))
          ?.slice(6)
          .trim();
        if (!type) continue; // SSE comment/heartbeat.
        let data: any;
        try {
          data = JSON.parse(
            lines
              .filter((l) => l.startsWith("data:"))
              .map((l) => l.slice(5).trimStart())
              .join("\n"),
          );
        } catch {
          throw new ChatStreamError(
            "protocol",
            "The API returned an invalid stream.",
          );
        }
        if (type === "error") {
          const status = typeof data.status === "number" ? data.status : 502;
          const detail =
            data.code === "timeout"
              ? "The request timed out. You can regenerate the response."
              : data.code === "storage"
                ? "Conversation storage is unavailable. Reopen before retrying."
                : statusMessage(status);
          throw new ChatStreamError(
            String(data.code),
            detail,
            status,
            data.retry_after,
          );
        }
        if (
          type === "start" &&
          !started &&
          validStoredMessage(data.user) &&
          data.user.role === "user" &&
          validStoredMessage(data.assistant) &&
          data.assistant.role === "assistant"
        ) {
          started = true;
          assistantId = data.assistant.id;
          onEvent({
            type: "start",
            user: data.user,
            assistant: data.assistant,
          });
        } else if (
          type === "delta" &&
          started &&
          data.id === assistantId &&
          typeof data.text === "string"
        ) {
          onEvent({ type: "delta", id: data.id, text: data.text });
        } else if (
          type === "done" &&
          started &&
          validStoredMessage(data.assistant) &&
          data.assistant.role === "assistant" &&
          data.assistant.id === assistantId &&
          data.assistant.status === "completed"
        ) {
          onEvent({ type: "done", assistant: data.assistant });
          return;
        } else
          throw new ChatStreamError(
            "protocol",
            "The API returned an invalid stream.",
          );
      }
      if (done)
        throw new ChatStreamError(
          "network",
          "The connection ended before generation completed. Reopen or regenerate the response.",
        );
    }
  } catch (e) {
    if (signal?.aborted)
      throw new DOMException("Request cancelled.", "AbortError");
    if (timedOut)
      throw new ChatStreamError(
        "timeout",
        "The request timed out. Reopen or regenerate the response.",
      );
    if (e instanceof ChatStreamError) throw e;
    throw new ChatStreamError(
      "network",
      "The connection was interrupted. Reopen or regenerate the response.",
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
    await reader?.cancel().catch(() => {});
    reader?.releaseLock();
  }
}
export const streamChatMessage = (
  message: string,
  token: string,
  id: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
  attachmentIds: string[] = [],
) => streamConversation(message, token, id, onEvent, signal, attachmentIds);
export const regenerateResponse = (
  token: string,
  id: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
) => streamConversation(null, token, id, onEvent, signal);

export type Attachment = {
  id: string;
  filename: string;
  media_type: string;
  size: number;
  width: number;
  height: number;
};
export type Project = {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
};
async function workspaceRequest<T>(
  path: string,
  token: string,
  method = "GET",
  body?: BodyInit,
  signal?: AbortSignal,
  type = "application/json",
): Promise<T> {
  if (!token.trim()) throw new Error("Sign in to access your workspace.");
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, CHAT_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}/api${path}`, {
      method,
      body,
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body ? { "Content-Type": type } : {}),
      },
    });
    if (!response.ok)
      throw new Error(
        response.status === 413
          ? "Image exceeds 2 MiB."
          : response.status === 415
            ? "Invalid image. Use PNG, JPEG or WebP."
            : response.status === 409
              ? "Remove the existing draft image first, or wait for generation to finish."
              : response.status === 404
                ? "Workspace item not found."
                : statusMessage(response.status),
      );
    return response.status === 204
      ? (undefined as T)
      : ((await response.json()) as T);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}
export const listProjects = (token: string, signal?: AbortSignal) =>
  workspaceRequest<Project[]>("/projects", token, "GET", undefined, signal);
export const createProject = (
  name: string,
  token: string,
  signal?: AbortSignal,
) =>
  workspaceRequest<Project>(
    "/projects",
    token,
    "POST",
    JSON.stringify({ name }),
    signal,
  );
export const renameProject = (
  id: string,
  name: string,
  token: string,
  signal?: AbortSignal,
) =>
  workspaceRequest<Project>(
    `/projects/${encodeURIComponent(id)}`,
    token,
    "PATCH",
    JSON.stringify({ name }),
    signal,
  );
export const deleteProject = (
  id: string,
  token: string,
  signal?: AbortSignal,
) =>
  workspaceRequest<void>(
    `/projects/${encodeURIComponent(id)}`,
    token,
    "DELETE",
    undefined,
    signal,
  );
export const updateConversation = (
  id: string,
  values: { project_id?: string | null; is_pinned?: boolean },
  token: string,
  signal?: AbortSignal,
) =>
  workspaceRequest<Conversation>(
    `/conversations/${encodeURIComponent(id)}`,
    token,
    "PATCH",
    JSON.stringify(values),
    signal,
  );
export const uploadAttachment = (
  id: string,
  file: File,
  token: string,
  signal?: AbortSignal,
) =>
  workspaceRequest<Attachment>(
    `/conversations/${encodeURIComponent(id)}/attachments?filename=${encodeURIComponent(file.name)}`,
    token,
    "POST",
    file,
    signal,
    file.type,
  );
export const discardAttachment = (
  id: string,
  aid: string,
  token: string,
  signal?: AbortSignal,
) =>
  workspaceRequest<void>(
    `/conversations/${encodeURIComponent(id)}/attachments/${encodeURIComponent(aid)}`,
    token,
    "DELETE",
    undefined,
    signal,
  );
export async function attachmentBlob(
  id: string,
  aid: string,
  token: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(id)}/attachments/${encodeURIComponent(aid)}`,
    { headers: { Authorization: `Bearer ${token}` }, signal },
  );
  if (!response.ok) throw new Error("Unable to load image.");
  return response.blob();
}
export const editResponse = (
  text: string,
  mid: string,
  token: string,
  id: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
) => streamConversation(text, token, id, onEvent, signal, [], mid);

export const listLibrary = (token: string, offset = 0, signal?: AbortSignal) =>
  workspaceRequest<Conversation[]>(
    `/library?offset=${offset}`,
    token,
    "GET",
    undefined,
    signal,
  );
