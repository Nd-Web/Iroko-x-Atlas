/**
 * app/(app)/knowledge-graph/page.tsx — the compliance knowledge graph.
 *
 * The page reads its tab and the open item from the URL (useSearchParams),
 * which Next.js requires to sit inside a Suspense boundary for production
 * builds. All data comes from /api/compliance-graph/*; nothing is mocked.
 */

import { Suspense } from "react";
import KnowledgeGraph from "@/components/compliance-graph/KnowledgeGraph";

function Fallback() {
  return (
    <div className="flex-1 p-6" role="status" aria-label="Loading the knowledge graph">
      <div className="h-6 w-48 animate-pulse rounded bg-gray-100" />
      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl border border-border-default bg-gray-50" />)}
      </div>
    </div>
  );
}

export default function KnowledgeGraphPage() {
  return (
    <Suspense fallback={<Fallback />}>
      <KnowledgeGraph />
    </Suspense>
  );
}
