import { useEffect, useRef, useState } from "react";

import { useEntraAuth } from "../auth/AuthProvider";
import { ChatIcon } from "./ChatIcon";
import { ChatComposer } from "./ChatComposer";
import { ChatEmptyState } from "./ChatEmptyState";
import { ChatMessage } from "./ChatMessage";
import { ChatSearch } from "./ChatSearch";
import { ChatSidebar, type SidebarProject } from "./ChatSidebar";
import { ChatProjectDialog } from "./ChatProjectDialog";
import type { ChatMessage as ChatMessageData } from "./types";
import "./chat.css";

import type { Conversation } from "../api";

type ChatPageProps = {
  projects?: SidebarProject[];
  pinnedChats?: import("./ChatSidebar").SidebarChat[];
  onCreateProject?: (name: string) => Promise<boolean>;
  onRenameProject?: (id: string, name: string) => void;
  onDeleteProject?: (id: string) => void;
  onMetadata?: (
    id: string,
    values: { project_id?: string | null; is_pinned?: boolean },
  ) => void;
  onEditMessage?: (id: string, text: string) => Promise<boolean>;
  conversations?: Conversation[];
  currentConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
  onLoadOlder?: () => void;
  onLoadMoreRecents?: () => void;
  isGenerating?: boolean;
  onStopGeneration?: () => void;
  onRegenerate?: () => void;
  notice?: string | null;
  error: string | null;
  isLoading: boolean;
  messages: ChatMessageData[];
  onNewConversation: () => void;
  onSendMessage: (message: string, file?: File | null) => Promise<boolean>;
};

export function ChatPage({
  projects = [],
  pinnedChats = [],
  onCreateProject,
  onRenameProject,
  onDeleteProject,
  onMetadata,
  onEditMessage,
  conversations = [],
  currentConversationId,
  onSelectConversation,
  onDeleteConversation,
  onLoadOlder,
  onLoadMoreRecents,
  isGenerating = false,
  onStopGeneration,
  onRegenerate,
  notice,
  error,
  isLoading,
  messages,
  onNewConversation,
  onSendMessage,
}: ChatPageProps): React.JSX.Element {
  const { account, authError, signOut } = useEntraAuth();
  const [image, setImage] = useState<File | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  useEffect(() => {
    setInput("");
    setImage(null);
    setEditing(null);
  }, [currentConversationId]);
  const [createProjectOpen, setCreateProjectOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [input, setInput] = useState("");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(max-width: 760px)").matches,
  );
  const conversationRef = useRef<HTMLDivElement>(null);
  const searchTarget = useRef<string | null>(null);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const submitting = useRef(false);
  const signingOut = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isMobile, setIsMobile] = useState(
    () => window.matchMedia("(max-width: 760px)").matches,
  );
  const sidebarModal = isMobile && !isSidebarCollapsed;
  const busy = isLoading || isSigningOut;
  const isEmpty = messages.length === 0;
  const lastUserIndex = messages.map((m) => m.role).lastIndexOf("user");
  const lastAssistantIndex = messages
    .map((m) => m.role)
    .lastIndexOf("assistant");

  const userName = account?.name ?? account?.username ?? "Signed-in user";

  useEffect(() => {
    const media = window.matchMedia("(max-width: 760px)");
    const update = () => {
      setIsMobile(media.matches);
      setIsSidebarCollapsed(media.matches);
    };
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (!sidebarModal) return;
    const sidebar = containerRef.current?.querySelector("aside");
    const controls = () =>
      Array.from(
        sidebar?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled)",
        ) ?? [],
      );
    controls()[0]?.focus();
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setIsSidebarCollapsed(true);
      } else if (event.key === "Tab") {
        const buttons = controls();
        const first = buttons[0];
        const last = buttons[buttons.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      containerRef.current
        ?.querySelector<HTMLButtonElement>(".chat-sidebar__mobile-open")
        ?.focus();
    };
  }, [sidebarModal]);

  async function handleSignOut() {
    if (signingOut.current) return;
    signingOut.current = true;
    setIsSigningOut(true);
    try {
      await signOut();
    } catch {
      // AuthProvider exposes the error to the sidebar.
    } finally {
      signingOut.current = false;
      setIsSigningOut(false);
    }
  }

  async function handleSubmit() {
    const message = input.trim();
    if ((!message && !image) || busy || submitting.current) return;
    submitting.current = true;
    try {
      const success = editing
        ? await onEditMessage?.(editing, message)
        : await onSendMessage(message, image);
      if (success) {
        setInput("");
        setImage(null);
        setEditing(null);
      }
    } finally {
      submitting.current = false;
    }
  }

  function handleNewConversation() {
    if (busy || submitting.current) return;

    setInput("");
    onNewConversation();
    if (isMobile) setIsSidebarCollapsed(true);
  }

  const nearBottom = useRef(true);
  const previousConversation = useRef(currentConversationId);
  const olderScroll = useRef<{ top: number; height: number } | null>(null);
  useEffect(() => {
    const element = conversationRef.current;
    if (!element) return;
    if (previousConversation.current !== currentConversationId) {
      nearBottom.current = true;
      previousConversation.current = currentConversationId;
    }
    if (olderScroll.current && messages.length) {
      const old = olderScroll.current;
      if (element.scrollHeight > old.height) {
        element.scrollTop = old.top + element.scrollHeight - old.height;
        olderScroll.current = null;
      }
    } else if (nearBottom.current) element.scrollTop = element.scrollHeight;
  }, [messages, isLoading, currentConversationId]);

  useEffect(() => {
    if (sidebarModal || !searchTarget.current) return;
    const target = document.getElementById(`message-${searchTarget.current}`);
    target?.scrollIntoView({ block: "center", behavior: "instant" });
    target?.focus({ preventScroll: true });
    searchTarget.current = null;
  }, [sidebarModal]);

  function selectMessage(id: string) {
    if (isMobile) {
      searchTarget.current = id;
      setIsSidebarCollapsed(true);
    } else {
      const target = document.getElementById(`message-${id}`);
      target?.scrollIntoView({ block: "center", behavior: "instant" });
      target?.focus({ preventScroll: true });
    }
  }

  return (
    <>
      <div
        inert={searchOpen || createProjectOpen}
        ref={containerRef}
        className={`chat-app${isSidebarCollapsed ? " chat-app--sidebar-collapsed" : ""}`}
      >
        <ChatSidebar
          conversations={conversations}
          currentConversationId={currentConversationId}
          onSelectConversation={(id) => {
            onSelectConversation?.(id);
            if (isMobile) setIsSidebarCollapsed(true);
          }}
          onDeleteConversation={onDeleteConversation}
          onLoadMoreRecents={onLoadMoreRecents}
          isModal={sidebarModal}
          authError={authError}
          isCollapsed={isSidebarCollapsed}
          isNewConversationDisabled={isLoading}
          isSigningOut={isSigningOut}
          onNewConversation={handleNewConversation}
          onSignOut={handleSignOut}
          onToggleCollapse={() => setIsSidebarCollapsed((current) => !current)}
          onSelectMessage={selectMessage}
          messages={messages}
          onOpenSearch={() => {
            if (isMobile) setIsSidebarCollapsed(true);
            setSearchOpen(true);
          }}
          projects={projects}
          pinnedChats={pinnedChats}
          onRenameProject={onRenameProject}
          onDeleteProject={onDeleteProject}
          onMetadata={onMetadata}
          onCreateProject={() => {
            if (isMobile) setIsSidebarCollapsed(true);
            setCreateProjectOpen(true);
          }}
          userName={userName}
        />
        {sidebarModal && (
          <button
            className="chat-sidebar__backdrop"
            type="button"
            tabIndex={-1}
            aria-label="Close sidebar"
            onClick={() => setIsSidebarCollapsed(true)}
          />
        )}
        <main
          className={`chat-shell${isEmpty ? " chat-shell--empty" : ""}`}
          inert={sidebarModal}
        >
          <header className="chat-topbar">
            <div className="chat-topbar__identity">
              <button
                aria-label="Open sidebar"
                className="chat-sidebar__mobile-open"
                type="button"
                aria-expanded={sidebarModal}
                aria-controls="chat-sidebar"
                onClick={() => setIsSidebarCollapsed(false)}
              >
                <ChatIcon name="sidebar" />
              </button>
              <span className="chat-topbar__name">Open Thread</span>
              <span className="chat-topbar__divider">/</span>
              <span className="chat-meta">Chat</span>
            </div>
            <span className="chat-topbar__session chat-meta">
              Saved conversations
            </span>
          </header>
          {error && isEmpty && (
            <p className="chat-error" role="alert">
              {error}
            </p>
          )}
          {isEmpty ? (
            <section className="chat-empty" aria-labelledby="chat-title">
              <ChatEmptyState
                input={input}
                image={image}
                onImage={setImage}
                isGenerating={isGenerating}
                onStop={onStopGeneration}
                isLoading={busy}
                onChange={setInput}
                onSubmit={handleSubmit}
              />
            </section>
          ) : (
            <section className="chat-workspace" aria-label="Conversation">
              <div
                onScroll={() => {
                  const e = conversationRef.current;
                  if (e)
                    nearBottom.current =
                      e.scrollHeight - e.scrollTop - e.clientHeight < 80;
                }}
                ref={conversationRef}
                className="chat-conversation"
                aria-live="polite"
                aria-busy={isLoading}
              >
                {onLoadOlder && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      const e = conversationRef.current;
                      if (e) {
                        olderScroll.current = {
                          top: e.scrollTop,
                          height: e.scrollHeight,
                        };
                        nearBottom.current = false;
                      }
                      onLoadOlder();
                    }}
                  >
                    Load older messages
                  </button>
                )}
                {messages.map((message, index) => (
                  <ChatMessage
                    message={message}
                    conversationId={currentConversationId}
                    onEdit={
                      onEditMessage &&
                      message.role === "user" &&
                      message.status !== "superseded"
                        ? () => {
                            setEditing(message.id);
                            setInput(message.text);
                            setImage(null);
                          }
                        : undefined
                    }
                    key={message.id}
                    busy={busy}
                    onRegenerate={
                      index === lastAssistantIndex && index > lastUserIndex
                        ? onRegenerate
                        : undefined
                    }
                  />
                ))}
                {isLoading && !isGenerating && (
                  <div
                    className="chat-message chat-message--assistant"
                    role="status"
                  >
                    <p className="chat-message__thinking">
                      <span aria-hidden="true" className="chat-thinking-dot" />
                      Thinking…
                    </p>
                  </div>
                )}
              </div>

              {notice && (
                <p className="chat-meta" role="status">
                  {notice}
                </p>
              )}
              {error && (
                <p className="chat-error" role="alert">
                  {error}
                </p>
              )}

              <div className="chat-followup">
                <ChatComposer
                  input={input}
                  image={image}
                  onImage={setImage}
                  editing={!!editing}
                  onCancelEdit={() => {
                    setEditing(null);
                    setInput("");
                  }}
                  isGenerating={isGenerating}
                  onStop={onStopGeneration}
                  isLoading={busy}
                  onChange={setInput}
                  onSubmit={handleSubmit}
                />
                <p className="chat-composer__hint">
                  AI responses can be inaccurate. Review important details.
                </p>
              </div>
            </section>
          )}
        </main>
      </div>
      {createProjectOpen && (
        <ChatProjectDialog
          onClose={() => setCreateProjectOpen(false)}
          onCreate={async (name) => {
            if (await onCreateProject?.(name)) {
              setCreateProjectOpen(false);
              if (isMobile) setIsSidebarCollapsed(false);
            }
          }}
        />
      )}
      {searchOpen && (
        <ChatSearch
          messages={messages}
          onClose={() => setSearchOpen(false)}
          onSelectMessage={(id) => {
            setSearchOpen(false);
            // Wait for the canvas to become interactive before focusing a result.
            requestAnimationFrame(() => selectMessage(id));
          }}
        />
      )}
    </>
  );
}
