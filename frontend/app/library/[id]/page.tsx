import { notFound } from "next/navigation";
import { Suspense } from "react";

import { PageContainer } from "@/components/layout/page-header";
import { DocumentDetailView } from "@/components/library/document-detail-view";
import { Skeleton } from "@/components/ui/states";

export default function DocumentPage({ params }: PageProps<"/library/[id]">) {
  // Route params are runtime data; reading them inside Suspense keeps the shell prerenderable.
  return (
    <Suspense
      fallback={
        <PageContainer>
          <Skeleton className="h-24" />
        </PageContainer>
      }
    >
      <DocumentFromParams params={params} />
    </Suspense>
  );
}

async function DocumentFromParams({ params }: { params: PageProps<"/library/[id]">["params"] }) {
  const { id } = await params;
  const documentId = Number(id);
  if (!Number.isInteger(documentId) || documentId < 1) notFound();
  return <DocumentDetailView id={documentId} />;
}
