/**
 * lib/sector.ts
 *
 * The compliance solution serves two regulated verticals:
 *   - "network"   → Nigerian network operators (e.g. MTN Nigeria), regulated by the NCC.
 *   - "financial" → African fintechs / MFBs, regulated by CBN & SEC.
 * NDPA (NDPC) data-protection obligations apply to both.
 *
 * The selected sector is persisted in localStorage and read by the useSector
 * hook. It is also forwarded to the backend compliance engine so verdicts are
 * grounded in the correct regulatory corpus.
 */

export type Sector = "network" | "financial";

export const SECTORS: Sector[] = ["network", "financial"];
export const DEFAULT_SECTOR: Sector = "network";
export const SECTOR_STORAGE_KEY = "iroko_sector";
/** Fired on the window when the sector changes, so same-tab consumers re-sync. */
export const SECTOR_EVENT = "iroko-sector-change";

export interface SectorMeta {
  id: Sector;
  /** Short pill label in the switcher. */
  short: string;
  /** Example organisation for this vertical. */
  org: string;
  /** Compliance agent page title. */
  agentTitle: string;
  /** Compliance agent page subtitle. */
  agentSubtitle: string;
  /** Reports page subtitle. */
  reportsSubtitle: string;
  /** Regulators cited in the live checker copy. */
  regulators: string;
  /** Placeholder for the checker textarea. */
  checkerPlaceholder: string;
  /** Context string sent to the backend (also used as the default org label). */
  checkerContext: string;
}

export const SECTOR_META: Record<Sector, SectorMeta> = {
  network: {
    id: "network",
    short: "MTN Nigeria",
    org: "MTN Nigeria",
    agentTitle: "Network Compliance Agent",
    agentSubtitle: "NCC · NDPA · DPO console · DPIA wizard · QoS & filing history",
    reportsSubtitle: "NCC returns · QoS filings · NDPA audit · DPIA tracker · DSR queue",
    regulators: "NCC · NDPA",
    checkerPlaceholder:
      "Describe the action, product, or policy you want to check against NCC/NDPA regulations...",
    checkerContext: "MTN Nigeria network compliance check",
  },
  financial: {
    id: "financial",
    short: "Financial",
    org: "African Fintech Platform",
    agentTitle: "Fintech Compliance Agent",
    agentSubtitle: "CBN · SEC · NDPA · DPO console · DPIA wizard · filing history",
    reportsSubtitle: "CBN returns · SEC filings · NDPA audit · DPIA tracker · DSR queue",
    regulators: "CBN · NCC · SEC · NDPA",
    checkerPlaceholder:
      "Describe the action, product, or policy you want to check against CBN/NCC regulations...",
    checkerContext: "Nigerian MFB compliance check",
  },
};

export function isSector(v: unknown): v is Sector {
  return v === "network" || v === "financial";
}
