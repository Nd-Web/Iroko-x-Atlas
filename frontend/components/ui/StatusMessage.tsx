/**
 * components/ui/StatusMessage.tsx
 *
 * Consistent success / error banner used across all forms in Iroko AI.
 *
 * Usage pattern in a form page:
 *
 *   const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
 *
 *   // Show the message then auto-dismiss after 3 seconds
 *   const showMessage = (type: "success" | "error", text: string) => {
 *     setMessage({ type, text });
 *     setTimeout(() => setMessage(null), 3000);
 *   };
 *
 *   {message && <StatusMessage type={message.type} text={message.text} />}
 */

"use client";

interface StatusMessageProps {
  type: "success" | "error";
  text: string;
}

export default function StatusMessage({ type, text }: StatusMessageProps) {
  const isSuccess = type === "success";

  return (
    <div
      role="alert"
      className={[
        "flex items-start gap-2.5 px-3.5 py-3 rounded-lg border text-[13px] leading-[1.5]",
        isSuccess
          ? "bg-success-50 border-success-100 text-success-700"
          : "bg-danger-50 border-danger-100 text-danger-700",
      ].join(" ")}
    >
      {/* Icon */}
      <svg
        width="16"
        height="16"
        viewBox="0 0 16 16"
        fill="none"
        className="shrink-0 mt-[1px]"
      >
        {isSuccess ? (
          <>
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.4" />
            <path
              d="M5 8l2 2 4-4"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        ) : (
          <>
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.4" />
            <path
              d="M8 5.5v3"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
            <circle cx="8" cy="11" r="0.75" fill="currentColor" />
          </>
        )}
      </svg>

      <span>{text}</span>
    </div>
  );
}
