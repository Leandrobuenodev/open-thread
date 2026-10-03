import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChatIcon } from "./ChatIcon";

type Props = {
  onClose: () => void;
  onCreate: (name: string) => void | Promise<boolean | void>;
};

export function ChatProjectDialog({ onClose, onCreate }: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const submitted = useRef(false);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.showModal();
    inputRef.current?.focus();
    return () => {
      requestAnimationFrame(() => {
        const target = window.matchMedia("(max-width: 760px)").matches
          ? document.querySelector<HTMLButtonElement>(
              ".chat-sidebar__mobile-open",
            )
          : previous;
        if (target?.isConnected && !target.closest("[inert]")) target.focus();
      });
    };
  }, []);
  return createPortal(
    <dialog
      ref={dialogRef}
      className="chat-project-modal"
      aria-labelledby="project-dialog-title"
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(
          dialogRef.current?.querySelectorAll<HTMLElement>(
            "button:not(:disabled), input",
          ) ?? [],
        );
        const first = controls[0],
          last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        className="chat-project-modal__content"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!name.trim() || submitted.current) return;
          submitted.current = true;
          setSaving(true);
          setError(null);
          try {
            const result = await onCreate(name.trim());
            if (result === false) {
              setError("Unable to save project. Try again.");
              submitted.current = false;
            }
          } catch {
            setError("Unable to save project. Try again.");
            submitted.current = false;
          } finally {
            setSaving(false);
          }
        }}
      >
        <header>
          <h2 id="project-dialog-title">Create project</h2>
          <button
            type="button"
            aria-label="Close create project"
            onClick={onClose}
          >
            ×
          </button>
        </header>
        <label htmlFor="project-name">Project name</label>
        <div className="chat-project-modal__input">
          <ChatIcon name="folder" />
          <input
            ref={inputRef}
            id="project-name"
            autoFocus
            autoComplete="off"
            maxLength={80}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Name your project"
          />
        </div>
        {error && <p role="alert">{error}</p>}
        <footer>
          <button type="submit" disabled={!name.trim() || saving}>
            Create project
          </button>
        </footer>
      </form>
    </dialog>,
    document.body,
  );
}
