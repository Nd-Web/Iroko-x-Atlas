"use client";

import { SECTORS, SECTOR_META, Sector } from "@/lib/sector";
import { useSector } from "@/hooks/useSector";

/**
 * Segmented control that switches the compliance solution between the
 * network-operator (MTN Nigeria / NCC) and financial-institution (CBN/SEC)
 * regulatory verticals. Selection is shared across the compliance pages.
 */
export default function SectorSwitcher() {
  const [sector, setSector] = useSector();

  return (
    <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-gray-100 border border-border-default">
      <span className="text-[10.5px] font-bold text-gray-400 uppercase tracking-[0.06em] pl-2 pr-1 hidden sm:inline">
        Sector
      </span>
      {SECTORS.map((s: Sector) => {
        const active = s === sector;
        return (
          <button
            key={s}
            onClick={() => setSector(s)}
            aria-pressed={active}
            className={`text-[12.5px] font-semibold px-3 py-[6px] rounded-md transition-colors ${
              active
                ? "bg-white text-brand-700 shadow-sm border border-border-default"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {SECTOR_META[s].short}
          </button>
        );
      })}
    </div>
  );
}
