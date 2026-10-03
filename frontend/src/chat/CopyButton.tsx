import { useEffect, useRef, useState } from "react";

export function CopyButton({
  text,
  label = "Copy",
}: {
  text: string;
  label?: string;
}) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setFeedback("Copied");
    } catch {
      setFeedback("Copy unavailable");
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setFeedback(null), 1800);
  }
  return (
    <button
      type="button"
      className="chat-message__action"
      aria-label={label}
      onClick={() => void copy()}
    >
      {feedback ?? "Copy"}
      <span className="chat-sr-only" role="status">
        {feedback}
      </span>
    </button>
  );
}
