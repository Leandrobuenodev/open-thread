import { useEffect, useState } from "react";
import { useEntraAuth } from "../auth/AuthProvider";
import { attachmentBlob, type Attachment } from "../api";
import { InterfaceIcon } from "../components/InterfaceIcon";
import { AssistantMarkdown } from "./AssistantMarkdown";
import { CopyButton } from "./CopyButton";
import type { ChatMessage as ChatMessageData } from "./types";

type ChatMessageProps = {
  message: ChatMessageData;
  onEdit?: () => void;
  conversationId?: string | null;
  onRegenerate?: () => void;
  busy?: boolean;
};
export function ChatMessage({
  message,
  onEdit,
  conversationId,
  onRegenerate,
  busy,
}: ChatMessageProps): React.JSX.Element {
  const assistant = message.role === "assistant";
  return (
    <article
      id={`message-${message.id}`}
      tabIndex={-1}
      aria-label={assistant ? "Open Thread response" : "Your message"}
      className={`chat-message chat-message--${message.role}${message.status === "superseded" ? " chat-message--superseded" : ""}`}
    >
      <p className="chat-message__label chat-meta">
        {assistant ? (
          <>
            <span aria-hidden="true">
              <InterfaceIcon name="brand" />
            </span>{" "}
            Open Thread
          </>
        ) : (
          "You"
        )}
      </p>
      <div className="chat-message__body">
        {assistant ? (
          <AssistantMarkdown text={message.text} />
        ) : (
          <p>{message.text}</p>
        )}
        {assistant && message.streaming && (
          <span
            className="chat-stream-cursor"
            aria-label="Generating response"
            role="status"
          />
        )}
      </div>
      {message.attachments?.map((a) => (
        <AttachmentImage
          key={a.id}
          attachment={a}
          conversationId={conversationId}
        />
      ))}
      {onEdit && (
        <button
          type="button"
          className="chat-message__action"
          disabled={busy}
          onClick={onEdit}
        >
          Edit
        </button>
      )}
      {message.status === "failed" && (
        <p className="chat-meta">
          {assistant
            ? "Generation failed. Partial response saved."
            : "Saved without an assistant response."}
        </p>
      )}
      {message.status === "cancelled" && (
        <p className="chat-meta">Generation stopped.</p>
      )}
      {message.status === "superseded" && (
        <p className="chat-meta">Previous version.</p>
      )}
      {message.status === "pending" && !message.streaming && (
        <p className="chat-meta">
          Response pending; reopen this conversation to check.
        </p>
      )}
      {assistant && !message.streaming && (
        <div className="chat-message__actions">
          {message.text && (
            <CopyButton text={message.text} label="Copy response" />
          )}
          {onRegenerate && (
            <button
              type="button"
              className="chat-message__action"
              disabled={busy || message.status === "pending"}
              onClick={onRegenerate}
            >
              Regenerate
            </button>
          )}
        </div>
      )}
    </article>
  );
}

function AttachmentImage({
  attachment,
  conversationId,
}: {
  attachment: Attachment;
  conversationId?: string | null;
}) {
  const { getAccessToken } = useEntraAuth();
  const [url, setUrl] = useState<string | null>(null),
    [error, setError] = useState(false);
  useEffect(() => {
    if (!conversationId) return;
    const controller = new AbortController();
    let objectUrl: string | undefined;
    void (async () => {
      try {
        const token = await getAccessToken();
        if (controller.signal.aborted) return;
        const blob = await attachmentBlob(
          conversationId,
          attachment.id,
          token,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      } catch {
        if (!controller.signal.aborted) setError(true);
      }
    })();
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [conversationId, attachment.id, getAccessToken]);
  return (
    <figure className="chat-attachment">
      {url ? (
        <img src={url} alt={attachment.filename} />
      ) : (
        <span>{error ? "Image unavailable" : "Loading image…"}</span>
      )}
      <figcaption>{attachment.filename}</figcaption>
    </figure>
  );
}
