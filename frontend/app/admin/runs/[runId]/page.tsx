import { notFound } from "next/navigation";

import { RunDetailPanel } from "@/components/run-detail-panel";
import { getBackendBaseUrl } from "@/lib/backend-url";
import type { RunDetailEnvelope } from "@/lib/run-detail";

type PageProps = {
  params: {
    runId: string;
  };
};

async function loadRunDetail(runId: string): Promise<RunDetailEnvelope | null> {
  const response = await fetch(`${getBackendBaseUrl()}/api/v1/admin/runs/${encodeURIComponent(runId)}`, {
    cache: "no-store",
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to load run detail (${response.status})`);
  }

  return (await response.json()) as RunDetailEnvelope;
}

export default async function RunDetailPage({ params }: PageProps) {
  const { runId } = params;

  try {
    const detail = await loadRunDetail(runId);
    if (detail === null) {
      notFound();
    }
    return <RunDetailPanel initialDetail={detail.data} requestId={detail.meta.request_id} />;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load run detail";
    return (
      <main className="app-shell">
        <div className="page">
          <section className="panel">
            <p className="kicker">Run Detail</p>
            <h1 className="title">Failed to load</h1>
            <p className="lede">{message}</p>
          </section>
        </div>
      </main>
    );
  }
}
