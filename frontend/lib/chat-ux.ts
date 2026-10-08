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
