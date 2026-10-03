// Local visual test fixture: no Entra account, token, backend or Foundry call.
import React from "react";
import { createRoot } from "react-dom/client";
import { ChatMessage } from "../../src/chat/ChatMessage";
import { ChatComposer } from "../../src/chat/ChatComposer";
import "../../src/chat/chat.css";
const text =
  '# Markdown\n\n**Bold**, *italic*, `inline` and [link](https://example.com).\n\n- First\n- Second\n\n> Quote\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```python\nprint("' +
  "long_code_".repeat(40) +
  '")\n```';
createRoot(document.getElementById("root")!).render(
  <main
    style={{
      fontFamily: "Instrument Sans Variable, sans-serif",
      maxWidth: 760,
      width: "calc(100% - 32px)",
      margin: "16px auto",
      boxSizing: "border-box",
    }}
  >
    <ChatMessage
      message={{ id: "local", role: "assistant", text, status: "completed" }}
      onRegenerate={() => {}}
    />
    <ChatComposer
      input=""
      isLoading
      isGenerating
      onChange={() => {}}
      onSubmit={() => {}}
      onStop={() => {}}
    />
  </main>,
);
