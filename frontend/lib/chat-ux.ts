export const CHAT_MAX_CHARS = 2000;

/** Enter submits, but never interrupt an IME composition or Shift+Enter. */
export function shouldSubmitChat(event: {
  key: string; shiftKey: boolean; altKey: boolean;
  nativeEvent: { isComposing?: boolean; keyCode?: number };
}) {
  return event.key === "Enter" && !event.shiftKey && !event.altKey
    && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229;
}

export function isNearChatBottom(scroll: {
  scrollHeight: number; scrollTop: number; clientHeight: number;
}) {
  return scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 100;
}

/** Keep the latest exchange in focus without deleting earlier conversation data. */
export function splitLatestExchange<T extends { role: string }>(messages: T[]) {
  const lastUserIndex = messages.map(message => message.role).lastIndexOf("user");
  return lastUserIndex > 0
    ? { previous: messages.slice(0, lastUserIndex), current: messages.slice(lastUserIndex) }
    : { previous: [] as T[], current: messages };
}

/** Find preceding questions in one pass rather than rescanning each prefix. */
export function previousQuestions(messages: readonly { id: string; role: string; content: string }[]) {
  const questions = new Map<string, string | undefined>();
  let previous: string | undefined;
  for (const message of messages) {
    questions.set(message.id, previous);
    if (message.role === "user") previous = message.content;
  }
  return questions;
}
