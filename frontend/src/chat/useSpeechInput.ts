import { useEffect, useRef, useState } from "react";

type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onresult:
    | ((event: {
        resultIndex: number;
        results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
      }) => void)
    | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};
export function useSpeechInput(
  input: string,
  onChange: (text: string) => void,
  disabled: boolean,
) {
  const [recording, setRecording] = useState(false),
    [error, setError] = useState<string | null>(null);
  const active = useRef<Recognition | null>(null),
    change = useRef(onChange),
    current = useRef(input),
    cancelled = useRef(false);
  change.current = onChange;
  current.current = input;
  const Constructor =
    (window as SpeechWindow).SpeechRecognition ??
    (window as SpeechWindow).webkitSpeechRecognition;
  function cancel() {
    cancelled.current = true;
    active.current?.abort();
    active.current = null;
    setRecording(false);
  }
  useEffect(
    () => () => {
      cancelled.current = true;
      active.current?.abort();
    },
    [],
  );
  useEffect(() => {
    if (disabled) {
      cancelled.current = true;
      active.current?.abort();
      active.current = null;
      setRecording(false);
    }
  }, [disabled]);
  function start() {
    if (!Constructor || disabled || active.current) return;
    const recognition = new Constructor();
    active.current = recognition;
    cancelled.current = false;
    setError(null);
    recognition.lang = navigator.language || "pt-BR";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onstart = () => {
      if (!cancelled.current && active.current === recognition)
        setRecording(true);
    };
    recognition.onend = () => {
      if (active.current !== recognition) return;
      active.current = null;
      setRecording(false);
    };
    recognition.onerror = (event) => {
      if (cancelled.current || active.current !== recognition) return;
      setError(
        event.error === "not-allowed" || event.error === "service-not-allowed"
          ? "Microphone permission denied."
          : event.error === "no-speech"
            ? "No speech detected. Try again."
            : "Speech recognition failed. Try again.",
      );
      setRecording(false);
    };
    recognition.onresult = (event) => {
      if (cancelled.current || active.current !== recognition) return;
      let text = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) text += event.results[i][0].transcript;
      }
      if (text.trim())
        change.current(
          [current.current.trim(), text.trim()].filter(Boolean).join(" "),
        );
    };
    try {
      setRecording(true);
      recognition.start();
    } catch {
      active.current = null;
      setRecording(false);
      setError("Unable to start microphone.");
    }
  }
  return {
    supported: !!Constructor,
    recording,
    error,
    start,
    stop: () => active.current?.stop(),
    cancel,
  };
}
