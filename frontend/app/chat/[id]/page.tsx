// /chat/[id]: loads existing conversation by ID; streams response tokens
import { redirect } from "next/navigation";

/**
 * Individual conversation route — redirects to the main chat page.
 * The chat page manages conversation state via the useChat hook;
 * deep-linking to a specific conversation ID can be implemented here later.
 */
export default function ConversationPage({
  params,
}: {
  params: { id: string };
}) {
  // Redirect to main chat — conversation selection handled client-side
  redirect("/chat");
}