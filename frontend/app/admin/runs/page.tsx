import { notFound } from "next/navigation";

import { AdminRunsPanel } from "@/components/admin-runs-panel";
import { getBackendBaseUrl } from "@/lib/backend-url";
import {
  buildRunListSearchParams,
  normalizeRunListPage,
  type RunListFilters,
  type RunListPage,
} from "@/lib/admin-observability";

type QueryValue = string | string[] | undefined;

type PageProps = {
  searchParams?: Record<string, QueryValue>;
};

function firstSearchParam(value: QueryValue): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

function parseTriState(value: QueryValue): boolean | null | undefined {
  const text = firstSearchParam(value);
  if (text === "true") {
    return true;
  }
  if (text === "false") {
    return false;
  }
  return null;
}

function parseLimit(value: QueryValue): number | null {
  const text = firstSearchParam(value);
  if (!text) {
    return null;
  }
  const parsed = Number(text);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function toFilters(searchParams?: Record<string, QueryValue>): RunListFilters {
  return {
    status: firstSearchParam(searchParams?.status),
    createdFrom: firstSearchParam(searchParams?.created_from),
    createdTo: firstSearchParam(searchParams?.created_to),
    requesterId: firstSearchParam(searchParams?.requester_id),
    periodStart: firstSearchParam(searchParams?.period_start),
    periodEnd: firstSearchParam(searchParams?.period_end),
    hasHumanInput: parseTriState(searchParams?.has_human_input),
    hasRetry: parseTriState(searchParams?.has_retry),
    hasPartialFailure: parseTriState(searchParams?.has_partial_failure),
    cursor: firstSearchParam(searchParams?.cursor),
    limit: parseLimit(searchParams?.limit),
  };
}

async function loadRunListPage(filters: RunListFilters): Promise<RunListPage | null> {
  const query = buildRunListSearchParams(filters);
  const response = await fetch(`${getBackendBaseUrl()}/api/v1/admin/runs?${query}`, {
    cache: "no-store",
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to load run list (${response.status})`);
  }

  return normalizeRunListPage(await response.json());
}

export default async function RunsPage({ searchParams }: PageProps) {
  const filters = toFilters(searchParams);

  try {
    const page = await loadRunListPage(filters);
    if (page === null) {
      notFound();
    }

    return <AdminRunsPanel page={page} filters={filters} />;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load run list";
    return (
      <main className="app-shell">
        <div className="page">
          <section className="panel">
            <p className="kicker">Admin Runs</p>
            <h1 className="title">Failed to load</h1>
            <p className="lede">{message}</p>
          </section>
        </div>
      </main>
    );
  }
}
