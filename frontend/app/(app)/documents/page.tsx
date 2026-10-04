import DocumentsContent from "@/components/pages/DocumentsContent";
import AppShell from "@/components/layout/AppShell";

export const metadata = { title: "Documents" };

export default function DocumentsPage() {
  return (
    <AppShell title="Document library" subtitle="Indexed documents across your connected sources">
      <DocumentsContent />
    </AppShell>
  );
}
