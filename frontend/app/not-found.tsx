import Link from "next/link";

import { PageContainer } from "@/components/layout/page-header";

export default function NotFound() {
  return (
    <PageContainer>
      <div className="py-24 text-center">
        <p className="font-mono text-sm text-subtle-foreground">404</p>
        <h1 className="mt-2 text-xl font-semibold tracking-tight">Page not found</h1>
        <Link href="/" className="mt-4 inline-block text-sm text-accent hover:underline">
          Back to dashboard
        </Link>
      </div>
    </PageContainer>
  );
}
