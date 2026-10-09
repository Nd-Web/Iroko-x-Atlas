// Only official, server-owned public evidence links may leave the document library.
const regulators = new Set([
  "cbn.gov.ng", "www.cbn.gov.ng", "sec.gov.ng", "www.sec.gov.ng", "home.sec.gov.ng",
  "ndpc.gov.ng", "www.ndpc.gov.ng", "ndic.gov.ng", "www.ndic.gov.ng",
  "nfiu.gov.ng", "www.nfiu.gov.ng", "fccpc.gov.ng", "www.fccpc.gov.ng",
]);

/**
 * An Iroko compliance record (a confirmed link in the compliance graph) opens
 * inside the app. Only a same-origin /knowledge-graph path with a plain query
 * string is accepted; anything else is refused.
 */
export function recordUrl(provenance?: Record<string, unknown> | null): string | undefined {
  if (!provenance || provenance.source_kind !== "iroko_record") return undefined;
  const value = provenance.record_url;
  if (typeof value !== "string" || !/^\/knowledge-graph(?:\?[A-Za-z0-9=&_.%-]*)?$/.test(value)) return undefined;
  return value;
}

export function citationUrl(value?: string | null): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || !regulators.has(url.hostname) || url.username || url.password || (url.port && url.port !== "443")) return undefined;
    return url.href;
  } catch {
    return undefined;
  }
}
