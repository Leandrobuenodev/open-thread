type IconName =
  | "sidebar"
  | "new"
  | "search"
  | "pin"
  | "folder"
  | "chat"
  | "chevron"
  | "logout"
  | "arrow"
  | "microphone"
  | "attachment";
const paths: Record<IconName, React.ReactNode> = {
  sidebar: (
    <>
      <rect x="3" y="4" width="18" height="16" />
      <path d="M9 4v16" />
    </>
  ),
  new: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 4 4" />
    </>
  ),
  pin: <path d="m8 3 8 0-1 6 3 4H6l3-4-1-6Zm4 10v8" />,
  folder: <path d="M3 6h7l2 3h9v11H3V6Z" />,
  chat: <path d="M4 4h16v13H9l-5 4V4Z" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  logout: (
    <>
      <path d="M10 4H4v16h6m4-13 5 5-5 5M9 12h10" />
    </>
  ),
  microphone: (
    <>
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8" />
    </>
  ),
  attachment: (
    <path d="m8 12 7-7a4 4 0 0 1 6 6L10 22a6 6 0 0 1-8-8L13 3m-8 14 11-11" />
  ),
  arrow: <path d="M12 19V5m-6 6 6-6 6 6" />,
};
export function ChatIcon({ name }: { name: IconName }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="chat-icon">
      {paths[name]}
    </svg>
  );
}
