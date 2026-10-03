import { useSpeechInput } from "./useSpeechInput";
import { useState } from "react";
import { ChatIcon } from "./ChatIcon";

import {
  useEffect,
  useRef,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";

export type ChatComposerProps = {
  image?: File | null;
  onImage?: (file: File | null) => void;
  editing?: boolean;
  onCancelEdit?: () => void;
  input: string;
  isLoading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  isGenerating?: boolean;
  onStop?: () => void;
};

export function ChatComposer({
  image,
  onImage,
  editing,
  onCancelEdit,
  input,
  isGenerating = false,
  onStop,
  isLoading,
  onChange,
  onSubmit,
  placeholder = "Ask anything...",
}: ChatComposerProps): React.JSX.Element {
  const speech = useSpeechInput(input, onChange, isLoading);
  const [imageError, setImageError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!image) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);
  function choose(file?: File) {
    if (!file) return;
    if (
      !["image/png", "image/jpeg", "image/webp"].includes(file.type) ||
      file.size > 2 * 1024 * 1024
    ) {
      setImageError("Use PNG, JPEG or WebP up to 2 MiB.");
      return;
    }
    setImageError(null);
    onImage?.(file);
  }
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wasLoading = useRef(isLoading);

  useEffect(() => {
    if (wasLoading.current && !isLoading) textareaRef.current?.focus();
    wasLoading.current = isLoading;
  }, [isLoading]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 176)}px`;
    textarea.style.overflowY = textarea.scrollHeight > 176 ? "auto" : "hidden";
  }, [input]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isLoading && (input.trim() || image)) onSubmit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      event.nativeEvent.isComposing
    )
      return;

    event.preventDefault();
    if (!isLoading && (input.trim() || image)) onSubmit();
  }

  function handleChange(event: ChangeEvent<HTMLTextAreaElement>) {
    onChange(event.target.value);
  }

  return (
    <form
      className="chat-composer"
      onSubmit={handleSubmit}
      onDragOver={(e) => {
        if (onImage && !editing) e.preventDefault();
      }}
      onDrop={(e) => {
        e.preventDefault();
        if (!isLoading && !editing && onImage) {
          if (e.dataTransfer.files.length > 1)
            setImageError("One image per message.");
          else choose(e.dataTransfer.files[0]);
        }
      }}
    >
      {editing && (
        <p className="chat-meta">
          Editing message · subsequent messages will become previous versions.{" "}
          <button type="button" onClick={onCancelEdit}>
            Cancel edit
          </button>
        </p>
      )}
      {preview && (
        <div className="chat-image-preview">
          <img src={preview} alt="Image preview" />
          <button
            type="button"
            disabled={isLoading}
            onClick={() => onImage?.(null)}
          >
            Remove image
          </button>
        </div>
      )}
      {imageError && <p role="alert">{imageError}</p>}
      <div className="chat-composer__surface">
        <textarea
          ref={textareaRef}
          aria-label="Message"
          autoComplete="off"
          disabled={isLoading}
          maxLength={10_000}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          value={input}
        />
        <div className="chat-composer__toolbar">
          {onImage && !editing && (
            <label className="chat-tool-button" aria-label="Attach image">
              <ChatIcon name="attachment" />
              <input
                aria-label="Choose image"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={isLoading}
                onChange={(e) => {
                  choose(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </label>
          )}
          <button
            type="button"
            className="chat-tool-button"
            disabled={isLoading || !speech.supported}
            aria-label={
              speech.recording ? "Finish recording" : "Start microphone"
            }
            aria-pressed={speech.recording}
            title={
              speech.supported
                ? "Speech recognition may use your browser's online service."
                : "Speech recognition is unavailable in this browser."
            }
            onClick={speech.recording ? speech.stop : speech.start}
          >
            {speech.recording ? (
              <span className="chat-stop-icon" aria-hidden="true" />
            ) : (
              <ChatIcon name="microphone" />
            )}
          </button>
          {speech.recording && (
            <>
              <span role="status">Recording…</span>
              <button type="button" onClick={speech.cancel}>
                Cancel recording
              </button>
            </>
          )}

          <button
            aria-label={isGenerating ? "Stop generation" : "Send message"}
            className="chat-composer__send"
            disabled={!isGenerating && (isLoading || (!input.trim() && !image))}
            type={isGenerating ? "button" : "submit"}
            onClick={isGenerating ? onStop : undefined}
          >
            {isGenerating ? (
              <span className="chat-stop-icon" aria-hidden="true" />
            ) : isLoading ? (
              <span className="chat-composer__loading" aria-hidden="true" />
            ) : (
              <ChatIcon name="arrow" />
            )}
          </button>
        </div>
      </div>
      {speech.error && (
        <p className="chat-meta" role="alert">
          {speech.error}
        </p>
      )}
      {!speech.supported && <p className="chat-meta">Speech unavailable</p>}
    </form>
  );
}
