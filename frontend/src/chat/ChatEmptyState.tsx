import { ChatComposer, type ChatComposerProps } from "./ChatComposer";

type ChatEmptyStateProps = ChatComposerProps & {
  isGenerating?: boolean;
  onStop?: () => void;
  input: string;
  isLoading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ChatEmptyState({
  isGenerating,
  onStop,
  image,
  onImage,
  input,
  isLoading,
  onChange,
  onSubmit,
}: ChatEmptyStateProps): React.JSX.Element {
  return (
    <>
      <div className="chat-empty__intro">
        <h1 id="chat-title">What would you like to ask?</h1>
      </div>
      <ChatComposer
        image={image}
        onImage={onImage}
        isGenerating={isGenerating}
        onStop={onStop}
        input={input}
        isLoading={isLoading}
        onChange={onChange}
        onSubmit={onSubmit}
      />
      <p className="chat-composer__hint">
        Enter to send <span aria-hidden="true">·</span> Shift + Enter for a new
        line
      </p>
    </>
  );
}
