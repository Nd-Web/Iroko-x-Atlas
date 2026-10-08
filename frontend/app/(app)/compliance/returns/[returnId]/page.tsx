/**
 * app/(app)/compliance/returns/[returnId]/page.tsx
 *
 * One regulatory return being prepared. `?period=2026-09` opens (or resumes)
 * that period's draft; `?draft=<id>` resumes a specific draft.
 */

import FilingWorkspace from "@/components/compliance/returns/FilingWorkspace";

export default async function FilingPage({
  params,
  searchParams,
}: {
  params: Promise<{ returnId: string }>;
  searchParams: Promise<{ period?: string; draft?: string }>;
}) {
  const { returnId } = await params;
  const { period, draft } = await searchParams;
  return <FilingWorkspace returnId={returnId} period={period} draftId={draft} />;
}
