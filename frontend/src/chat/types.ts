export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  attachments?: import("../api").Attachment[];
  status?: "pending" | "completed" | "failed" | "cancelled" | "superseded";
  streaming?: boolean;
  sequence?: number;
  replyToId?: string | null;
};
