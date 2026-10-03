import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChatIcon } from "./ChatIcon";
import type { ChatMessage } from "./types";

type Props = {
  messages: ChatMessage[];
  onClose: () => void;
  onSelectMessage: (id: string) => void;
};

export function ChatSearch({ messages, onClose, onSelectMessage }: Props) {
  const [query, setQuery] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const callbacks = useRef(onClose);
  callbacks.current = onClose;
  const term = query.trim().toLocaleLowerCase();
  const current = messages.find((message) => message.role === "user");
  const results = term
    ? messages.filter((message) =>
        message.text.toLocaleLowerCase().includes(term),
      )
    : current
      ? [current]
      : [];

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        callbacks.current();
      }
      const controls = Array.from(
        panelRef.current?.querySelectorAll<HTMLElement>("input, button") ?? [],
      );
      const index = controls.indexOf(document.activeElement as HTMLElement);
      if (event.key === "Tab") {
        if (event.shiftKey && index === 0) {
          event.preventDefault();
          controls.at(-1)?.focus();
        } else if (!event.shiftKey && index === controls.length - 1) {
          event.preventDefault();
          controls[0]?.focus();
        }
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const items = Array.from(
          panelRef.current?.querySelectorAll<HTMLButtonElement>(
            ".chat-search__result",
          ) ?? [],
        );
        if (!items.length) return;
        const active = items.indexOf(
          document.activeElement as HTMLButtonElement,
        );
        items[
          (active + (event.key === "ArrowDown" ? 1 : -1) + items.length) %
            items.length
        ]?.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      requestAnimationFrame(() => {
        const returnTarget = window.matchMedia("(max-width: 760px)").matches
          ? document.querySelector<HTMLButtonElement>(
              ".chat-sidebar__mobile-open",
            )
          : previous;
        if (returnTarget?.isConnected && !returnTarget.closest("[inert]"))
          returnTarget.focus();
      });
    };
  }, []);

  return createPortal(
    <div
      className="chat-search"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        className="chat-search__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-search-title"
      >
        <h2 id="chat-search-title" className="chat-search__sr">
          Search session chats
        </h2>
        <div className="chat-search__field">
          <ChatIcon name="search" />
          <input
            ref={inputRef}
            type="search"
            aria-label="Search messages"
            placeholder="Search session chats..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="button" aria-label="Close search" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="chat-search__results">
          <h3>{term ? "Matching messages" : "Recent chats"}</h3>
          {results.length ? (
            results.map((message) => (
              <button
                key={message.id}
                type="button"
                className="chat-search__result"
                onClick={() => onSelectMessage(message.id)}
              >
                <ChatIcon name="chat" />
                <span>{message.text}</span>
              </button>
            ))
          ) : (
            <p>
              {term
                ? "No matching messages."
                : "No conversations in this session yet."}
            </p>
          )}
          <p className="chat-search__note">
            Only the current session is available. Chats aren’t saved.
          </p>
          <span role="status" className="chat-search__sr">
            {term ? `${results.length} matching messages` : ""}
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
