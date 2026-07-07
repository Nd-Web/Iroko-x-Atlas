// /chat/[id]: deep link to an existing conversation.
import { redirect } from "next/navigation";

/**
 * Individual conversation route — forwards to the main chat page with a
 * `conv` query param. The chat page loads the conversation history via
 * GET /api/atlas/conversations/{id}/messages (cookie-auth proxy).
 */
export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  // In Next.js 16 dynamic routes, params is a Promise
  const { id } = await params;
  redirect(`/chat?conv=${encodeURIComponent(id)}`);
}
