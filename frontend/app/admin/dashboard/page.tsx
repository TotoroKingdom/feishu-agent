import { notFound } from "next/navigation";

import { AdminDashboardPanel } from "@/components/admin-dashboard-panel";
import { getBackendBaseUrl } from "@/lib/backend-url";
import {
  getDefaultDashboardWindow,
  normalizeDashboardSnapshot,
  type DashboardSnapshot,
} from "@/lib/admin-observability";

type QueryValue = string | string[] | undefined;

type PageProps = {
  searchParams?: {
    from?: QueryValue;
    to?: QueryValue;
  };
};

async function loadDashboardSnapshot(from: string, to: string): Promise<DashboardSnapshot | null> {
  const params = new URLSearchParams({ from, to });
  const response = await fetch(`${getBackendBaseUrl()}/api/v1/admin/dashboard?${params.toString()}`, {
    cache: "no-store",
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to load dashboard (${response.status})`);
  }

  return normalizeDashboardSnapshot(await response.json());
}

function firstSearchParam(value: QueryValue): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default async function DashboardPage({ searchParams }: PageProps) {
  const defaults = getDefaultDashboardWindow();
  const from = firstSearchParam(searchParams?.from) ?? defaults.from ?? "";
  const to = firstSearchParam(searchParams?.to) ?? defaults.to ?? "";

  try {
    const snapshot = await loadDashboardSnapshot(from, to);
    if (snapshot === null) {
      notFound();
    }

    return <AdminDashboardPanel snapshot={snapshot} from={from} to={to} />;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load dashboard";
    return (
      <main className="app-shell">
        <div className="page">
          <section className="panel">
            <p className="kicker">Admin Dashboard</p>
            <h1 className="title">Failed to load</h1>
            <p className="lede">{message}</p>
          </section>
        </div>
      </main>
    );
  }
}
