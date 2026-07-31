export type DashboardWindow = {
  from: string | null;
  to: string | null;
};

export type DashboardRunRow = {
  run_id: string;
  project_id: string;
  period_key: string;
  status: string;
  current_stage: string;
  current_node?: string | null;
  requester_id?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  created_at?: string | null;
  latest_activity_at?: string | null;
  completed_at?: string | null;
  has_human_input?: boolean;
  has_retry?: boolean;
  has_partial_failure?: boolean;
};

export type DashboardSnapshot = {
  window: DashboardWindow;
  recentRuns: DashboardRunRow[];
  metrics: {
    successRate: number;
    averageActiveDurationMs: number;
    waitingApprovals: number;
    toolFailureRate: number;
    retryCount: number;
    qualityDistribution: Array<{ label: string; count: number }>;
    tokenUsage: {
      input_tokens: number | null;
      output_tokens: number | null;
      total_tokens: number | null;
    };
  };
  requestId: string | null;
};

export type DashboardSummaryCard = {
  label: string;
  value: string;
  tone: "default" | "success" | "warning" | "danger";
};

export type DashboardSummary = {
  windowLabel: string;
  metricCards: DashboardSummaryCard[];
  recentRuns: Array<
    DashboardRunRow & {
      runId: string;
      headline: string;
      statusLabel: string;
      stageLabel: string;
      nodeLabel: string;
      activityLabel: string;
      periodLabel: string;
      requesterLabel: string;
      badges: string[];
    }
  >;
  qualityBuckets: Array<{ label: string; count: number }>;
  tokenSummary: Array<{ label: string; value: string }>;
};

export type RunListFilters = {
  status?: string | null;
  createdFrom?: string | null;
  createdTo?: string | null;
  requesterId?: string | null;
  periodStart?: string | null;
  periodEnd?: string | null;
  hasHumanInput?: boolean | null;
  hasRetry?: boolean | null;
  hasPartialFailure?: boolean | null;
  cursor?: string | null;
  limit?: number | null;
};

export type RunListRow = {
  run_id: string;
  project_id: string;
  period_key: string;
  status: string;
  current_stage: string;
  current_node?: string | null;
  requester_id?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  created_at?: string | null;
  latest_activity_at?: string | null;
  completed_at?: string | null;
  has_human_input?: boolean;
  has_retry?: boolean;
  has_partial_failure?: boolean;
};

export type RunListPage = {
  items: RunListRow[];
  nextCursor: string | null;
  hasMore: boolean;
  limit: number;
  requestId: string | null;
};

export type RunListSummaryRow = RunListRow & {
  runId: string;
  headline: string;
  statusLabel: string;
  stageLabel: string;
  nodeLabel: string;
  activityLabel: string;
  periodLabel: string;
  requesterLabel: string;
  badges: string[];
};

export type ObservabilitySectionKey =
  | "timeline"
  | "nodes"
  | "tools"
  | "llm-executions"
  | "diagnoses"
  | "approvals"
  | "evidence"
  | "artifacts"
  | "side-effects"
  | "publish-plan";

export type ObservabilitySectionConfig = {
  key: ObservabilitySectionKey;
  label: string;
  path: string;
  kind: "page" | "single";
};

export declare function getDefaultDashboardWindow(
  referenceDate?: Date,
): DashboardWindow;
export declare function buildDashboardSearchParams(window?: {
  from?: string | null;
  to?: string | null;
}): string;
export declare function buildRunListSearchParams(filters?: RunListFilters): string;
export declare function normalizeDashboardSnapshot(payload: unknown): DashboardSnapshot;
export declare function summarizeDashboardSnapshot(snapshot: DashboardSnapshot): DashboardSummary;
export declare function normalizeRunListPage(payload: unknown): RunListPage;
export declare function summarizeRunListRow(row: RunListRow): RunListSummaryRow;
export declare function getRunObservabilitySectionConfig(
  section: ObservabilitySectionKey | string,
): ObservabilitySectionConfig;
export declare function getRunObservabilitySections(): ObservabilitySectionConfig[];
export declare function buildRunObservabilityPath(
  runId: string,
  section: ObservabilitySectionKey | string,
  cursor?: string | null,
  limit?: number,
): string;
