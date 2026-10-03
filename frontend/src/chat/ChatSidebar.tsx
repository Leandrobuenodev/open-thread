import { InterfaceIcon } from "../components/InterfaceIcon";
import { useEffect, useRef, useState } from "react";
import { ChatIcon } from "./ChatIcon";
import type { ChatMessage } from "./types";

export type SidebarChat = { id: string; title: string; messageId: string };
export type SidebarProject = { id: string; name: string; chats: SidebarChat[] };

import type { Conversation } from "../api";

type ChatSidebarProps = {
  conversations?: Conversation[];
  currentConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
  onLoadMoreRecents?: () => void;
  authError: string | null;
  isCollapsed: boolean;
  isModal?: boolean;
  isNewConversationDisabled: boolean;
  isSigningOut: boolean;
  onNewConversation: () => void;
  onSignOut: () => Promise<void>;
  onToggleCollapse: () => void;
  onSelectMessage: (id: string) => void;
  messages: ChatMessage[];
  onOpenSearch: () => void;
  userName: string;
  pinnedChats?: SidebarChat[];
  projects?: SidebarProject[];
  onCreateProject?: () => void;
  onRenameProject?: (id: string, name: string) => void;
  onDeleteProject?: (id: string) => void;
  onMetadata?: (
    id: string,
    values: { project_id?: string | null; is_pinned?: boolean },
  ) => void;
};

export function ChatSidebar({
  conversations = [],
  currentConversationId,
  onSelectConversation,
  onDeleteConversation,
  onLoadMoreRecents,
  authError,
  isCollapsed,
  isModal = false,
  isNewConversationDisabled,
  isSigningOut,
  onNewConversation,
  onSignOut,
  onToggleCollapse,
  onSelectMessage,
  onOpenSearch,
  userName,
  pinnedChats = [],
  projects = [],
  onCreateProject,
  onRenameProject,
  onDeleteProject,
  onMetadata,
}: ChatSidebarProps) {
  const [pinnedOpen, setPinnedOpen] = useState(false);
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(
    new Set(),
  );
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);

  const initials = userName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("");

  useEffect(() => {
    if (projects.length) setProjectsOpen(true);
  }, [projects.length]);

  useEffect(() => {
    if (!accountOpen) return;
    function close(event: PointerEvent) {
      if (!accountRef.current?.contains(event.target as Node))
        setAccountOpen(false);
    }
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [accountOpen]);

  return (
    <aside
      id="chat-sidebar"
      aria-label="Open Thread sidebar"
      className={`chat-sidebar${isCollapsed ? " chat-sidebar--collapsed" : ""}`}
      role={isModal ? "dialog" : undefined}
      aria-modal={isModal || undefined}
    >
      <div className="chat-sidebar__content">
        <header className="chat-sidebar__header">
          <div className="chat-sidebar__brand">
            <span aria-hidden="true">
              <InterfaceIcon name="brand" />
            </span>
            <span className="chat-sidebar__label">Open Thread</span>
          </div>
          <button
            className="chat-sidebar__icon-button"
            type="button"
            aria-label={
              isCollapsed
                ? "Expand sidebar"
                : isModal
                  ? "Close sidebar"
                  : "Collapse sidebar"
            }
            aria-expanded={!isCollapsed}
            aria-controls="chat-sidebar"
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={onToggleCollapse}
          >
            {isCollapsed && (
              <span className="chat-sidebar__rail-symbol" aria-hidden="true">
                <InterfaceIcon name="brand" />
              </span>
            )}
            <ChatIcon name="sidebar" />
          </button>
        </header>
        <nav className="chat-sidebar__actions" aria-label="Chat actions">
          <button
            className="chat-sidebar__new"
            type="button"
            aria-label="New chat"
            title="New chat"
            disabled={isNewConversationDisabled || isSigningOut}
            onClick={onNewConversation}
          >
            <ChatIcon name="new" />
            <span className="chat-sidebar__label">New chat</span>
          </button>
          <button
            className="chat-sidebar__action"
            type="button"
            aria-label="Search this conversation"
            title="Search this conversation"
            aria-haspopup="dialog"
            onClick={onOpenSearch}
          >
            <ChatIcon name="search" />
            <span className="chat-sidebar__label">Search</span>
          </button>
        </nav>
        {!isCollapsed && (
          <div className="chat-sidebar__library">
            {pinnedChats.length > 0 && (
              <section
                className="chat-sidebar__section"
                aria-label="Pinned chats"
              >
                <button
                  type="button"
                  className="chat-sidebar__section-toggle"
                  aria-expanded={pinnedOpen}
                  aria-controls="chat-pinned"
                  onClick={() => setPinnedOpen((value) => !value)}
                >
                  <ChatIcon name="pin" />
                  <span>Pinned</span>
                  <span
                    className={`chat-sidebar__chevron${pinnedOpen ? " is-open" : ""}`}
                  >
                    <ChatIcon name="chevron" />
                  </span>
                </button>
                {pinnedOpen && (
                  <div id="chat-pinned">
                    {pinnedChats.map((chat) => (
                      <button
                        key={chat.id}
                        type="button"
                        className="chat-sidebar__current"
                        onClick={() =>
                          onSelectConversation
                            ? onSelectConversation(chat.id)
                            : onSelectMessage(chat.messageId)
                        }
                      >
                        <ChatIcon name="chat" />
                        <span>{chat.title}</span>
                      </button>
                    ))}
                  </div>
                )}
              </section>
            )}
            <section className="chat-sidebar__section">
              <div className="chat-sidebar__projects-header">
                <button
                  type="button"
                  className="chat-sidebar__section-toggle"
                  aria-expanded={projectsOpen}
                  aria-controls="chat-projects"
                  onClick={() => setProjectsOpen((value) => !value)}
                >
                  <ChatIcon name="folder" />
                  <span>Projects</span>
                  <span
                    className={`chat-sidebar__chevron${projectsOpen ? " is-open" : ""}`}
                  >
                    <ChatIcon name="chevron" />
                  </span>
                </button>
                <button
                  type="button"
                  className="chat-sidebar__project-add"
                  aria-label="Create project"
                  aria-haspopup="dialog"
                  onClick={onCreateProject}
                >
                  <ChatIcon name="new" />
                </button>
              </div>
              {projectsOpen && (
                <div id="chat-projects">
                  {projects.length ? (
                    projects.map((project) => {
                      const open = expandedProjects.has(project.id);
                      return (
                        <div key={project.id} className="chat-sidebar__project">
                          <button
                            type="button"
                            className="chat-sidebar__section-toggle"
                            aria-expanded={open}
                            aria-controls={`project-${project.id}`}
                            onClick={() =>
                              setExpandedProjects((current) => {
                                const next = new Set(current);
                                if (next.has(project.id))
                                  next.delete(project.id);
                                else next.add(project.id);
                                return next;
                              })
                            }
                          >
                            <span
                              className={`chat-sidebar__chevron${open ? " is-open" : ""}`}
                            >
                              <ChatIcon name="chevron" />
                            </span>
                            <ChatIcon name="folder" />
                            <span className="chat-sidebar__project-name">
                              {project.name}
                            </span>
                          </button>
                          {onRenameProject && (
                            <button
                              type="button"
                              disabled={isNewConversationDisabled}
                              aria-label={`Rename project: ${project.name}`}
                              onClick={() => {
                                const name = window.prompt(
                                  "Project name",
                                  project.name,
                                );
                                if (name?.trim())
                                  onRenameProject(project.id, name.trim());
                              }}
                            >
                              Rename
                            </button>
                          )}
                          {onDeleteProject && (
                            <button
                              type="button"
                              disabled={isNewConversationDisabled}
                              aria-label={`Delete project: ${project.name}`}
                              onClick={() => {
                                if (
                                  window.confirm(
                                    "Delete project? Conversations will be kept.",
                                  )
                                )
                                  onDeleteProject(project.id);
                              }}
                            >
                              Delete
                            </button>
                          )}
                          {open && (
                            <div
                              id={`project-${project.id}`}
                              className="chat-sidebar__project-chats"
                            >
                              {project.chats.length ? (
                                project.chats.map((chat) => (
                                  <button
                                    key={chat.id}
                                    type="button"
                                    className="chat-sidebar__current"
                                    onClick={() =>
                                      onSelectConversation
                                        ? onSelectConversation(chat.id)
                                        : onSelectMessage(chat.messageId)
                                    }
                                  >
                                    <span>{chat.title}</span>
                                  </button>
                                ))
                              ) : (
                                <p className="chat-sidebar__empty">
                                  No chats in this project yet.
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <p className="chat-sidebar__empty">No projects yet.</p>
                  )}
                </div>
              )}
            </section>
            <section
              className="chat-sidebar__section"
              aria-labelledby="recents-label"
            >
              <h2 id="recents-label">Recents</h2>
              {conversations.map((chat) => (
                <div key={chat.id} className="chat-sidebar__recent-row">
                  <button
                    className="chat-sidebar__current"
                    type="button"
                    aria-current={
                      chat.id === currentConversationId ? "page" : undefined
                    }
                    disabled={isNewConversationDisabled || isSigningOut}
                    title={chat.title}
                    onClick={() => onSelectConversation?.(chat.id)}
                  >
                    <ChatIcon name="chat" />
                    <span>{chat.title}</span>
                  </button>
                  {onMetadata && (
                    <>
                      <button
                        type="button"
                        disabled={isNewConversationDisabled}
                        aria-label={`${chat.is_pinned ? "Unpin" : "Pin"} conversation: ${chat.title}`}
                        onClick={() =>
                          onMetadata(chat.id, { is_pinned: !chat.is_pinned })
                        }
                      >
                        {chat.is_pinned ? "Unpin" : "Pin"}
                      </button>
                      <select
                        aria-label={`Project for conversation: ${chat.title}`}
                        disabled={isNewConversationDisabled}
                        value={chat.project_id ?? ""}
                        onChange={(e) =>
                          onMetadata(chat.id, {
                            project_id: e.target.value || null,
                          })
                        }
                      >
                        <option value="">No project</option>
                        {projects.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    </>
                  )}
                  {onDeleteConversation && (
                    <button
                      type="button"
                      aria-label={`Delete conversation: ${chat.title}`}
                      disabled={isNewConversationDisabled || isSigningOut}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Delete this conversation and all its messages?",
                          )
                        )
                          onDeleteConversation(chat.id);
                      }}
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              {!conversations.length && (
                <p className="chat-sidebar__empty">
                  No saved conversations yet.
                </p>
              )}
              {onLoadMoreRecents && (
                <button
                  type="button"
                  disabled={isNewConversationDisabled}
                  onClick={onLoadMoreRecents}
                >
                  Load more conversations
                </button>
              )}
            </section>
          </div>
        )}
        <div
          ref={accountRef}
          className="chat-sidebar__account"
          onKeyDown={(event) => {
            if (event.key === "Escape" && accountOpen) {
              event.stopPropagation();
              setAccountOpen(false);
              accountRef.current?.querySelector("button")?.focus();
            }
          }}
        >
          {authError && (
            <p className="chat-sidebar__error" role="alert">
              {authError}
            </p>
          )}
          <button
            type="button"
            className="chat-sidebar__user"
            aria-label={`Account: ${userName}`}
            title={userName}
            aria-expanded={accountOpen}
            aria-controls="chat-account-actions"
            onClick={() => setAccountOpen((value) => !value)}
          >
            <span className="chat-sidebar__avatar" aria-hidden="true">
              {initials}
            </span>
            <span className="chat-sidebar__label chat-sidebar__user-name">
              {userName}
            </span>
            <span className="chat-sidebar__label">
              <ChatIcon name="chevron" />
            </span>
          </button>
          {accountOpen && (
            <div
              id="chat-account-actions"
              className="chat-sidebar__account-menu"
            >
              <button
                className="chat-sidebar__signout"
                disabled={isSigningOut}
                type="button"
                onClick={() => void onSignOut()}
              >
                <ChatIcon name="logout" />
                {isSigningOut ? "Signing out…" : "Sign out"}
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
