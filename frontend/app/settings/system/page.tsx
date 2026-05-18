import AppShell from "@/components/layout/AppShell";

export const metadata = { title: "System Settings" };

const ROUTER = [
  { label: "Single-fact lookup",       tier: "Standard",   desc: "High volume, low-ambiguity queries",              color: "#17B26A" },
  { label: "Synthesis (3–10 chunks)",  tier: "Advanced",   desc: "Multi-source answers requiring reasoning",         color: "#4A55D4" },
  { label: "High-stakes / compliance", tier: "Compliance", desc: "Regulator-facing, dual-model critique applied",   color: "#F79009" },
  { label: "Multilingual generation",  tier: "Advanced",   desc: "Pidgin, Yoruba, Hausa, Igbo outputs",             color: "#4A55D4" },
];

const ATLAS_AGENTS = [
  { name: "Strategist", role: "Orchestrator",   desc: "Decomposes complex queries and synthesises responses", color: "#4A55D4" },
  { name: "Researcher", role: "Retrieval",      desc: "Executes hybrid search across Azure AI Search",         color: "#2E90FA" },
  { name: "Analyst",    role: "Data Analysis",  desc: "Extracts quantitative insights and identifies patterns", color: "#17B26A" },
  { name: "Scribe",     role: "Generation",     desc: "Produces cited reports and compliance drafts",         color: "#F79009" },
  { name: "Watchdog",   role: "Hallucination",  desc: "Verifies citation coverage and retrieval confidence",   color: "#F04438" },
];

const SOVEREIGNTY = [
  { label: "Deployment topology",    value: "Regional (West Africa)" },
  { label: "Nigeria-only routing",   value: "Enforced"           },
  { label: "Real-time signal window", value: "15 minutes"        },
  { label: "Retrieval top-k",        value: "10 chunks"          },
];

export default function SystemSettingsPage() {
  return (
    <AppShell title="System settings" subtitle="LLM router · sovereignty · multi-agent config">
      <div className="max-w-[700px] flex flex-col gap-6 mx-auto lg:mx-0 pb-10">
        
        {/* Atlas Multi-Agent System */}
        <div className="card overflow-hidden">
          <div className="py-[18px] px-5 md:px-6 border-b border-border-default bg-gray-50/50">
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Atlas Multi-Agent System</h2>
            <p className="text-xs text-gray-400 mt-[3px]">Functional AI roles built on Microsoft Semantic Kernel</p>
          </div>
          <div className="px-3 md:px-5 py-4 flex flex-col gap-2">
            {ATLAS_AGENTS.map((a) => (
              <div key={a.name} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 hover:bg-gray-50 rounded-lg transition-colors border border-transparent hover:border-border-default">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="size-8 rounded-lg flex items-center justify-center shrink-0 font-bold text-[11px]" style={{ background: `${a.color}15`, color: a.color, border: `1px solid ${a.color}25` }}>
                    {a.name[0]}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[13.5px] font-bold text-gray-900">{a.name}</span>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{a.role}</span>
                    </div>
                    <p className="text-[12px] text-gray-500 leading-normal">{a.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* LLM Router */}
        <div className="card overflow-hidden">
          <div className="py-[18px] px-5 md:px-6 border-b border-border-default">
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">LLM router policy</h2>
            <p className="text-xs text-gray-400 mt-[3px]">Automatic capability tier selection</p>
          </div>
          <div className="px-3 md:px-5 py-4 flex flex-col gap-[10px]">
            {ROUTER.map((r) => (
              <div key={r.label} className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 px-4 py-[13px] bg-gray-50 rounded-lg border border-border-default">
                <div className="flex items-start gap-3 min-w-0">
                  <div
                    className="size-2 rounded-[2px] mt-1.5 shrink-0"
                    style={{ background: r.color }}
                  />
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold text-gray-700 mb-[2px] truncate">{r.label}</div>
                    <div className="text-xs text-gray-400 truncate md:whitespace-normal">{r.desc}</div>
                  </div>
                </div>
                <span
                  className="font-mono text-[10px] md:text-[11px] font-semibold px-[10px] py-[3px] rounded-full shrink-0 w-fit"
                  style={{ color: r.color, background: `${r.color}14` }}
                >
                  {r.tier}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Data sovereignty */}
        <div className="card overflow-hidden">
          <div className="py-[18px] px-5 md:px-6 border-b border-border-default">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Data sovereignty</h2>
              <span className="text-[11px] font-semibold text-success-700 bg-success-50 px-[7px] py-[1px] rounded-full">Enforced</span>
            </div>
            <p className="text-xs text-gray-400">Regional jurisdiction processing</p>
          </div>
          <div className="py-1">
            {SOVEREIGNTY.map((s, i, arr) => (
              <div key={s.label} className={`flex justify-between items-center px-5 md:px-6 py-[13px] gap-4${i < arr.length - 1 ? " border-b border-border-default" : ""}`}>
                <span className="text-[13px] text-gray-500 truncate">{s.label}</span>
                <span className="text-[12px] md:text-[13px] font-semibold text-gray-800 font-mono text-right">{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
