interface AgentCardProps {
  label: string;
  href: string;
  description: string;
  statusColor: string;
  statusLabel: string;
  count: string;
  icon: React.ReactNode;
}

export default function AgentCard({
  label,
  href,
  description,
  statusColor,
  statusLabel,
  count,
  icon,
}: AgentCardProps) {
  return (
    <a
      href={href}
      className="card flex flex-col gap-3 py-[18px] px-5 no-underline cursor-pointer transition-all hover:shadow-md hover:border-gray-200"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[10px]">
          <div className="size-9 rounded-md bg-brand-50 flex items-center justify-center text-brand-600">
            {icon}
          </div>
          <span className="text-sm font-semibold text-gray-800">
            {label}
          </span>
        </div>
        <span className="text-xs font-semibold text-gray-500">
          {count}
        </span>
      </div>
      <p className="text-[13px] text-gray-400 leading-[1.5] m-0">
        {description}
      </p>
      <div className="flex items-center gap-1.5">
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: statusColor }}
        />
        <span className="text-xs text-gray-400">
          {statusLabel}
        </span>
      </div>
    </a>
  );
}
