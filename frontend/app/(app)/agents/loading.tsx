/**
 * app/(app)/loading.tsx
 *
 * Instant navigation feedback: shown in the content column (the sidebar and
 * topbar stay put) while the next page's code and server payload load.
 */

export default function Loading() {
  return (
    <main
      id="main-content"
      aria-busy="true"
      aria-label="Loading"
      className="flex-1 p-4 md:p-6 lg:p-7 flex flex-col gap-6 max-w-[1600px] mx-auto w-full overflow-hidden"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="h-24 rounded-xl bg-surface-card border border-border-default animate-pulse" />
        ))}
      </div>
      <div className="h-72 rounded-xl bg-surface-card border border-border-default animate-pulse" />
    </main>
  );
}
