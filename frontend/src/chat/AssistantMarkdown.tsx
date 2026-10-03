import { Children, isValidElement, useMemo, type ReactNode } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { createLowlight } from "lowlight";
import javascript from "highlight.js/lib/languages/javascript";
import typescript from "highlight.js/lib/languages/typescript";
import python from "highlight.js/lib/languages/python";
import json from "highlight.js/lib/languages/json";
import bash from "highlight.js/lib/languages/bash";
import sql from "highlight.js/lib/languages/sql";
import css from "highlight.js/lib/languages/css";
import xml from "highlight.js/lib/languages/xml";
import type { RootContent } from "hast";
import { CopyButton } from "./CopyButton";

const highlighter = createLowlight({
  javascript,
  typescript,
  python,
  json,
  bash,
  sql,
  css,
  xml,
});
const aliases: Record<string, string> = {
  js: "javascript",
  jsx: "javascript",
  ts: "typescript",
  tsx: "typescript",
  py: "python",
  sh: "bash",
  shell: "bash",
  html: "xml",
  svg: "xml",
};
function token(node: RootContent, key: number): ReactNode {
  if (node.type === "text") return node.value;
  if (node.type !== "element") return null;
  const classes = node.properties.className;
  return (
    <span
      key={key}
      className={Array.isArray(classes) ? classes.join(" ") : undefined}
    >
      {node.children.map(token)}
    </span>
  );
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const canonical = aliases[language] ?? language;
  const highlighted = useMemo(
    () =>
      highlighter.registered(canonical)
        ? highlighter.highlight(canonical, code).children.map(token)
        : code,
    [code, canonical],
  );
  return (
    <div className="chat-message__code">
      <div className="chat-message__code-toolbar">
        <span className="chat-meta">{language || "Code"}</span>
        <CopyButton text={code} label="Copy code" />
      </div>
      <pre tabIndex={0} aria-label={`${language || "Plain text"} code`}>
        <code className={canonical ? `language-${canonical}` : undefined}>
          {highlighted}
        </code>
      </pre>
    </div>
  );
}

export function AssistantMarkdown({ text }: { text: string }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        img: () => null,
        a: ({ node: _node, ...props }) => (
          <a {...props} target="_blank" rel="noopener noreferrer" />
        ),
        pre: ({ children }) => {
          const child = Children.toArray(children)[0];
          if (
            !isValidElement<{ className?: string; children?: ReactNode }>(child)
          )
            return <pre>{children}</pre>;
          const language =
            /language-([\w+-]+)/
              .exec(child.props.className ?? "")?.[1]
              ?.toLowerCase() ?? "";
          const code = String(child.props.children ?? "").replace(/\n$/, "");
          return <CodeBlock code={code} language={language} />;
        },
        table: ({ children }) => (
          <div className="chat-markdown__table">
            <table>{children}</table>
          </div>
        ),
      }}
    >
      {text}
    </Markdown>
  );
}
