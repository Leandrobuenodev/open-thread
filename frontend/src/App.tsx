import { useEffect, useRef, useState } from "react";
import {
  listLibrary,
  listProjects,
  createProject,
  renameProject,
  deleteProject,
  updateConversation,
  uploadAttachment,
  editResponse,
  type Project,
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  streamChatMessage,
  regenerateResponse,
  type StreamEvent,
  type Conversation,
  type ConversationDetail,
} from "./api";
import { useEntraAuth } from "./auth/AuthProvider";
import { ChatPage } from "./chat/ChatPage";
import type { ChatMessage } from "./chat/types";

function displayMessages(detail: ConversationDetail): ChatMessage[] {
  return detail.messages.map((m) => ({
    id: m.id,
    role: m.role,
    text: m.content,
    status: m.status,
    replyToId: m.reply_to_id,
    sequence: m.sequence,
    attachments: m.attachments,
  }));
}

export default function App() {
  const { getAccessToken } = useEntraAuth();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [library, setLibrary] = useState<Conversation[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [moreRecents, setMoreRecents] = useState(false);
  const pending = useRef<AbortController | null>(null);
  const generation = useRef<AbortController | null>(null);
  const stopped = useRef(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const tokenGetter = useRef(getAccessToken);
  tokenGetter.current = getAccessToken;

  function selectId(id: string | null) {
    setConversationId(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("conversation", id);
    else url.searchParams.delete("conversation");
    window.history.replaceState(null, "", url);
  }

  useEffect(() => {
    const request = new AbortController();
    pending.current = request;
    void (async () => {
      try {
        const token = await tokenGetter.current();
        if (request.signal.aborted) return;
        const rows = await listConversations(token, 0, request.signal);
        if (request.signal.aborted) return;
        setProjects(await listProjects(token, request.signal));
        await refreshLibrary(token, request.signal);
        setConversations(rows);
        setMoreRecents(rows.length === 50);
        // A URL stores only the selected ID; ownership is always checked by the API.
        const selected = new URL(window.location.href).searchParams.get(
          "conversation",
        );
        const id =
          selected && /^[0-9a-f-]{36}$/i.test(selected)
            ? selected
            : rows[0]?.id;
        if (id) {
          let detail: ConversationDetail;
          try {
            detail = await getConversation(
              id,
              token,
              undefined,
              request.signal,
            );
          } catch (e) {
            if (
              !(e instanceof Error) ||
              e.message !== "Conversation not found."
            )
              throw e;
            if (!rows[0]) {
              selectId(null);
              return;
            }
            detail = await getConversation(
              rows[0].id,
              token,
              undefined,
              request.signal,
            );
          }
          if (request.signal.aborted) return;
          show(detail);
        }
      } catch (e) {
        if (!request.signal.aborted)
          setError(
            e instanceof Error ? e.message : "Unable to load conversations.",
          );
      } finally {
        if (pending.current === request) {
          pending.current = null;
          if (!request.signal.aborted) setIsLoading(false);
        }
      }
    })();
    return () => {
      request.abort();
      pending.current?.abort();
      generation.current?.abort();
    };
    // AuthGate remounts App when the authenticated account changes.
  }, []);

  async function operation(
    work: (token: string, signal: AbortSignal) => Promise<void>,
  ): Promise<boolean> {
    if (pending.current) return false;
    const request = new AbortController();
    pending.current = request;
    setIsLoading(true);
    setError(null);
    setNotice(null);
    try {
      const token = await tokenGetter.current();
      if (request.signal.aborted) return false;
      await work(token, request.signal);
      return !request.signal.aborted;
    } catch (e) {
      if (!request.signal.aborted)
        setError(
          e instanceof Error ? e.message : "Conversation request failed.",
        );
      return false;
    } finally {
      if (pending.current === request) {
        pending.current = null;
        if (!request.signal.aborted) setIsLoading(false);
      }
    }
  }

  function show(detail: ConversationDetail) {
    selectId(detail.id);
    setMessages(displayMessages(detail));
    setNextBefore(detail.next_before);
  }

  async function refreshLibrary(token: string, signal: AbortSignal) {
    const all: Conversation[] = [];
    for (let offset = 0; !signal.aborted; offset += 50) {
      const rows = await listLibrary(token, offset, signal);
      all.push(...rows);
      if (rows.length < 50) break;
    }
    if (!signal.aborted) setLibrary(all);
  }

  async function refresh(token: string, signal: AbortSignal) {
    const rows = await listConversations(token, 0, signal);
    const savedProjects = await listProjects(token, signal);
    await refreshLibrary(token, signal);
    if (!signal.aborted) setProjects(savedProjects);
    if (!signal.aborted) {
      setConversations(rows);
      setMoreRecents(rows.length === 50);
    }
  }

  function streamEvent(event: StreamEvent) {
    if (event.type === "start") {
      const rows = [event.user, event.assistant].map((m) => ({
        id: m.id,
        role: m.role,
        text: m.content,
        status: m.status,
        replyToId: m.reply_to_id,
        sequence: m.sequence,
        attachments: m.attachments,
        streaming: true,
      }));
      setMessages((current) =>
        [
          ...current.map((m) => rows.find((row) => row.id === m.id) ?? m),
          ...rows.filter((row) => !current.some((m) => m.id === row.id)),
        ].sort(
          (a, b) =>
            (a.sequence ?? Number.MAX_SAFE_INTEGER) -
            (b.sequence ?? Number.MAX_SAFE_INTEGER),
        ),
      );
    } else if (event.type === "delta") {
      setMessages((current) =>
        current.map((m) =>
          m.id === event.id ? { ...m, text: m.text + event.text } : m,
        ),
      );
    } else {
      setMessages((current) =>
        current.map((m) =>
          m.id === event.assistant.id
            ? {
                ...m,
                text: event.assistant.content,
                status: event.assistant.status,
                streaming: false,
              }
            : m,
        ),
      );
    }
  }

  async function generate(
    message: string | null,
    file?: File | null,
    editId?: string,
  ): Promise<boolean> {
    return operation(async (token, signal) => {
      let id = conversationId;
      if (!id && message !== null) {
        const created = await createConversation(token, signal);
        if (signal.aborted) return;
        id = created.id;
        selectId(id);
      }
      if (!id) return;
      const attachmentIds: string[] = [];
      if (file && !editId && message !== null) {
        const attachment = await uploadAttachment(id, file, token, signal);
        attachmentIds.push(attachment.id);
      }
      if (editId) {
        setMessages((current) => {
          const original = current.find((m) => m.id === editId);
          return current.map((m) =>
            original && (m.sequence ?? 0) >= (original.sequence ?? 0)
              ? { ...m, status: "superseded" }
              : m,
          );
        });
      }
      const controller = new AbortController();
      generation.current = controller;
      stopped.current = false;
      const abort = () => controller.abort();
      signal.addEventListener("abort", abort, { once: true });
      setIsGenerating(true);
      let failure: unknown;
      try {
        if (editId)
          await editResponse(
            message ?? "",
            editId,
            token,
            id,
            streamEvent,
            controller.signal,
          );
        else if (message === null)
          await regenerateResponse(token, id, streamEvent, controller.signal);
        else
          await streamChatMessage(
            message,
            token,
            id,
            streamEvent,
            controller.signal,
            attachmentIds,
          );
      } catch (e) {
        if (!stopped.current) failure = e;
      } finally {
        signal.removeEventListener("abort", abort);
        generation.current = null;
        if (!signal.aborted) {
          setIsGenerating(false);
          setMessages((current) =>
            current.map((m) => ({ ...m, streaming: false })),
          );
        }
      }
      if (signal.aborted) return;
      try {
        // Disconnect finalization is asynchronous. Read back the server's terminal
        // state without retrying inference or duplicating the saved prompt.
        let detail = await getConversation(id, token, undefined, signal);
        for (
          let n = 0;
          n < 20 &&
          stopped.current &&
          detail.messages.some((m) => m.status === "pending");
          n++
        ) {
          await new Promise((resolve) => setTimeout(resolve, 100));
          if (signal.aborted) return;
          detail = await getConversation(id, token, undefined, signal);
        }
        if (signal.aborted) return;
        show(detail);
        await refresh(token, signal);
        if (stopped.current)
          setNotice(
            detail.messages.some((m) => m.status === "pending")
              ? "Stop requested. Reopen this conversation to check its saved state."
              : detail.messages.at(-1)?.status === "completed"
                ? "The response completed before Stop reached the server."
                : "Generation stopped. Partial response saved.",
          );
      } catch (e) {
        failure ??= e;
      }
      if (failure) throw failure;
    });
  }

  async function handleSendMessage(
    message: string,
    file?: File | null,
  ): Promise<boolean> {
    const prompt = message.trim();
    if ((!prompt && !file) || new TextEncoder().encode(prompt).length > 512) {
      setError("Use a message of at most 512 UTF-8 bytes.");
      return false;
    }
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const lastAssistant = [...messages]
      .reverse()
      .find((m) => m.role === "assistant");
    const retry =
      lastUser?.text === prompt &&
      (lastUser.status === "failed" ||
        lastUser.status === "cancelled" ||
        lastAssistant?.status === "failed" ||
        lastAssistant?.status === "cancelled");
    // An explicit resend of a failed/stopped latest prompt is a new assistant
    // attempt, preserving the original user row. No automatic inference retries.
    return generate(retry && !file ? null : prompt, file);
  }

  return (
    <ChatPage
      projects={projects.map((p) => ({
        ...p,
        chats: library
          .filter((c) => c.project_id === p.id)
          .map((c) => ({ id: c.id, title: c.title, messageId: c.id })),
      }))}
      pinnedChats={library
        .filter((c) => c.is_pinned)
        .map((c) => ({ id: c.id, title: c.title, messageId: c.id }))}
      onCreateProject={(name) =>
        operation(async (token, signal) => {
          await createProject(name, token, signal);
          await refresh(token, signal);
        })
      }
      onRenameProject={(id, name) => {
        void operation(async (token, signal) => {
          await renameProject(id, name, token, signal);
          await refresh(token, signal);
        });
      }}
      onDeleteProject={(id) => {
        void operation(async (token, signal) => {
          await deleteProject(id, token, signal);
          await refresh(token, signal);
        });
      }}
      onMetadata={(id, values) => {
        void operation(async (token, signal) => {
          await updateConversation(id, values, token, signal);
          await refresh(token, signal);
        });
      }}
      onEditMessage={(id, text) => generate(text, null, id)}

      isGenerating={isGenerating}
      notice={notice}
      onStopGeneration={() => {
        if (generation.current) {
          stopped.current = true;
          generation.current.abort();
        }
      }}
      onRegenerate={() => {
        void generate(null);
      }}
      error={error}
      isLoading={isLoading}
      messages={messages}
      conversations={conversations}
      currentConversationId={conversationId}
      onNewConversation={() => {
        void operation(async (token, signal) => {
          const c = await createConversation(token, signal);
          if (!signal.aborted) {
            selectId(c.id);
            setMessages([]);
            setNextBefore(null);
          }
          await refresh(token, signal);
        });
      }}
      onSelectConversation={(id) => {
        void operation(async (token, signal) => {
          const detail = await getConversation(id, token, undefined, signal);
          if (!signal.aborted) show(detail);
        });
      }}
      onDeleteConversation={(id) => {
        void operation(async (token, signal) => {
          await deleteConversation(id, token, signal);
          if (!signal.aborted && id === conversationId) {
            selectId(null);
            setMessages([]);
            setNextBefore(null);
          }
          await refresh(token, signal);
        });
      }}
      onLoadOlder={
        nextBefore
          ? () => {
              void operation(async (token, signal) => {
                if (!conversationId) return;
                const detail = await getConversation(
                  conversationId,
                  token,
                  nextBefore,
                  signal,
                );
                if (!signal.aborted) {
                  setMessages((current) => [
                    ...displayMessages(detail),
                    ...current,
                  ]);
                  setNextBefore(detail.next_before);
                }
              });
            }
          : undefined
      }
      onLoadMoreRecents={
        moreRecents
          ? () => {
              void operation(async (token, signal) => {
                const rows = await listConversations(
                  token,
                  conversations.length,
                  signal,
                );
                if (!signal.aborted) {
                  setConversations((current) => [
                    ...current,
                    ...rows.filter((r) => !current.some((c) => c.id === r.id)),
                  ]);
                  setMoreRecents(rows.length === 50);
                }
              });
            }
          : undefined
      }
      onSendMessage={handleSendMessage}
    />
  );
}
