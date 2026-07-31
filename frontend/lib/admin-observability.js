import { getRunStatusLabel } from "./run-detail.js";

const DASHBOARD_WINDOW_DAYS = 30;
const DEFAULT_RUN_LIST_LIMIT = 20;
const MAX_RUN_LIST_LIMIT = 100;

const SECTION_CONFIGS = [
  { key: "timeline", label: "Timeline", path: "timeline", kind: "page" },
  { key: "nodes", label: "Nodes", path: "nodes", kind: "page" },
  { key: "tools", label: "Tools", path: "tools", kind: "page" },
  { key: "llm-executions", label: "LLM", path: "llm-executions", kind: "page" },
  { key: "diagnoses", label: "Diagnoses", path: "diagnoses", kind: "page" },
  { key: "approvals", label: "Approvals", path: "approvals", kind: "page" },
  { key: "evidence", label: "Evidence", path: "evidence", kind: "page" },
  { key: "artifacts", label: "Artifacts", path: "artifacts", kind: "page" },
  { key: "side-effects", label: "Side Effects", path: "side-effects", kind: "page" },
  { key: "publish-plan", label: "Publish Plan", path: "publish-plan", kind: "single" },
];

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function unwrapDataEnvelope(payload) {
  if (isPlainObject(payload) && "data" in payload) {
    return payload.data;
  }
  return payload;
}

function normalizeDateText(value) {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function toUtcDateText(value) {
  return `${value.getUTCFullYear()}-${pad2(value.getUTCMonth() + 1)}-${pad2(value.getUTCDate())}`;
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  return `${(Number(value) * 100).toFixed(1).replace(/\.0$/, "")}%`;
}

function formatCount(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US").format(Number(value));
}

function formatDurationMs(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  const numeric = Number(value);
  if (numeric < 1000) {
    return `${numeric}ms`;
  }
  if (numeric < 60_000) {
    return `${(numeric / 1000).toFixed(1).replace(/\.0$/, "")}s`;
  }
  return `${(numeric / 60_000).toFixed(1).replace(/\.0$/, "")}m`;
}

function normalizeBooleanText(value) {
  if (value === true || value === "true" || value === 1 || value === "1") {
    return "true";
  }
  if (value === false || value === "false" || value === 0 || value === "0") {
    return "false";
  }
  return null;
}

function normalizePositiveInteger(value, fallback) {
  const numeric = Number(value);
  if (Number.isInteger(numeric) && numeric > 0) {
    return numeric;
  }
  return fallback;
}

function normalizeRunRow(row) {
  return {
    run_id: String(row?.run_id ?? row?.id ?? ""),
    project_id: String(row?.project_id ?? ""),
    period_key: String(row?.period_key ?? ""),
    status: String(row?.status ?? "unknown"),
    current_stage: String(row?.current_stage ?? "n/a"),
    current_node: normalizeDateText(row?.current_node),
    requester_id: normalizeDateText(row?.requester_id),
    period_start: normalizeDateText(row?.period_start),
    period_end: normalizeDateText(row?.period_end),
    created_at: normalizeDateText(row?.created_at),
    latest_activity_at: normalizeDateText(row?.latest_activity_at),
    completed_at: normalizeDateText(row?.completed_at),
    has_human_input: Boolean(row?.has_human_input),
    has_retry: Boolean(row?.has_retry),
    has_partial_failure: Boolean(row?.has_partial_failure),
  };
}

function normalizeQualityDistribution(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => ({
      label: String(item?.label ?? item?.status ?? "unknown"),
      count: Number(item?.count ?? item?.value ?? 0),
    }))
    .filter((item) => item.label.length > 0);
}

function normalizeTokenUsage(value) {
  if (!isPlainObject(value)) {
    return {
      input_tokens: null,
      output_tokens: null,
      total_tokens: null,
    };
  }
  return {
    input_tokens: Number.isFinite(Number(value.input_tokens)) ? Number(value.input_tokens) : null,
    output_tokens: Number.isFinite(Number(value.output_tokens)) ? Number(value.output_tokens) : null,
    total_tokens: Number.isFinite(Number(value.total_tokens)) ? Number(value.total_tokens) : null,
  };
}

function normalizeMetricSource(source) {
  const metrics = isPlainObject(source?.metrics)
    ? source.metrics
    : isPlainObject(source?.summary)
      ? source.summary
      : source;
  return {
    successRate: Number(metrics?.success_rate ?? metrics?.successRate ?? NaN),
    averageActiveDurationMs: Number(
      metrics?.average_active_duration_ms ?? metrics?.averageActiveDurationMs ?? NaN,
    ),
    waitingApprovals: Number(metrics?.waiting_approvals ?? metrics?.waitingApprovals ?? NaN),
    toolFailureRate: Number(metrics?.tool_failure_rate ?? metrics?.toolFailureRate ?? NaN),
    retryCount: Number(metrics?.retry_count ?? metrics?.retries ?? NaN),
    qualityDistribution: normalizeQualityDistribution(
      metrics?.quality_distribution ?? metrics?.qualityDistribution ?? source?.quality_distribution,
    ),
    tokenUsage: normalizeTokenUsage(
      metrics?.token_usage ?? metrics?.tokenUsage ?? source?.token_usage ?? source?.tokenUsage,
    ),
  };
}

export function getDefaultDashboardWindow(referenceDate = new Date()) {
  const current = new Date(
    Date.UTC(
      referenceDate.getUTCFullYear(),
      referenceDate.getUTCMonth(),
      referenceDate.getUTCDate(),
    ),
  );
  const from = new Date(current);
  from.setUTCDate(from.getUTCDate() - DASHBOARD_WINDOW_DAYS);
  return {
    from: toUtcDateText(from),
    to: toUtcDateText(current),
  };
}

export function buildDashboardSearchParams(window = {}) {
  const resolved = {
    ...getDefaultDashboardWindow(),
    from: normalizeDateText(window.from) ?? getDefaultDashboardWindow().from,
    to: normalizeDateText(window.to) ?? getDefaultDashboardWindow().to,
  };
  const params = new URLSearchParams();
  params.set("from", resolved.from);
  params.set("to", resolved.to);
  return params.toString();
}

export function buildRunListSearchParams(filters = {}) {
  const params = new URLSearchParams();
  const entries = [
    ["status", normalizeDateText(filters.status)],
    ["created_from", normalizeDateText(filters.createdFrom)],
    ["created_to", normalizeDateText(filters.createdTo)],
    ["requester_id", normalizeDateText(filters.requesterId)],
    ["period_start", normalizeDateText(filters.periodStart)],
    ["period_end", normalizeDateText(filters.periodEnd)],
    ["has_human_input", normalizeBooleanText(filters.hasHumanInput)],
    ["has_retry", normalizeBooleanText(filters.hasRetry)],
    ["has_partial_failure", normalizeBooleanText(filters.hasPartialFailure)],
    ["cursor", normalizeDateText(filters.cursor)],
  ];

  for (const [key, value] of entries) {
    if (value) {
      params.set(key, value);
    }
  }

  const limit = normalizePositiveInteger(filters.limit, DEFAULT_RUN_LIST_LIMIT);
  params.set("limit", String(Math.min(limit, MAX_RUN_LIST_LIMIT)));
  return params.toString();
}

export function normalizeDashboardSnapshot(payload) {
  const source = unwrapDataEnvelope(payload) ?? {};
  const windowSource = isPlainObject(source?.window) ? source.window : source;
  const recentRunsSource = Array.isArray(source?.recent_runs)
    ? source.recent_runs
    : Array.isArray(source?.runs)
      ? source.runs
      : [];

  return {
    window: {
      from: normalizeDateText(windowSource?.from),
      to: normalizeDateText(windowSource?.to),
    },
    recentRuns: recentRunsSource.map((row) => normalizeRunRow(row)),
    metrics: normalizeMetricSource(source),
    requestId: isPlainObject(payload) && isPlainObject(payload.meta) ? normalizeDateText(payload.meta.request_id) : null,
  };
}

export function summarizeDashboardSnapshot(snapshot) {
  const windowLabel =
    snapshot?.window?.from && snapshot?.window?.to
      ? `${snapshot.window.from} -> ${snapshot.window.to}`
      : "n/a";
  const recentRuns = Array.isArray(snapshot?.recentRuns)
    ? snapshot.recentRuns.map((row) => summarizeRunListRow(row))
    : [];
  const metricCards = [
    {
      label: "Recent runs",
      value: formatCount(recentRuns.length),
      tone: "default",
    },
    {
      label: "Success rate",
      value: formatPercent(snapshot?.metrics?.successRate),
      tone: "success",
    },
    {
      label: "Avg active time",
      value: formatDurationMs(snapshot?.metrics?.averageActiveDurationMs),
      tone: "default",
    },
    {
      label: "Waiting approvals",
      value: formatCount(snapshot?.metrics?.waitingApprovals),
      tone: "warning",
    },
    {
      label: "Tool failure rate",
      value: formatPercent(snapshot?.metrics?.toolFailureRate),
      tone: "danger",
    },
    {
      label: "Retries",
      value: formatCount(snapshot?.metrics?.retryCount),
      tone: "default",
    },
  ];
  const qualityBuckets = Array.isArray(snapshot?.metrics?.qualityDistribution)
    ? snapshot.metrics.qualityDistribution
    : [];
  const tokenSummary = [
    { label: "Input", value: formatCount(snapshot?.metrics?.tokenUsage?.input_tokens) },
    { label: "Output", value: formatCount(snapshot?.metrics?.tokenUsage?.output_tokens) },
    { label: "Total", value: formatCount(snapshot?.metrics?.tokenUsage?.total_tokens) },
  ];

  return {
    windowLabel,
    metricCards,
    recentRuns,
    qualityBuckets,
    tokenSummary,
  };
}

export function normalizeRunListPage(payload) {
  const source = unwrapDataEnvelope(payload) ?? {};
  const itemsSource = Array.isArray(source?.items)
    ? source.items
    : Array.isArray(source)
      ? source
      : Array.isArray(payload?.data)
        ? payload.data
        : [];
  const pageSource = isPlainObject(payload?.page)
    ? payload.page
    : isPlainObject(source?.page)
      ? source.page
      : {};

  return {
    items: itemsSource.map((row) => normalizeRunRow(row)),
    nextCursor: normalizeDateText(pageSource?.next_cursor),
    hasMore: Boolean(pageSource?.has_more),
    limit: normalizePositiveInteger(pageSource?.limit, itemsSource.length || DEFAULT_RUN_LIST_LIMIT),
    requestId: isPlainObject(payload) && isPlainObject(payload.meta) ? normalizeDateText(payload.meta.request_id) : null,
  };
}

export function summarizeRunListRow(row) {
  const badges = [];
  if (row?.has_human_input) {
    badges.push("HITL");
  }
  if (row?.has_retry) {
    badges.push("Retry");
  }
  if (row?.has_partial_failure) {
    badges.push("Partial failure");
  }

  return {
    runId: row?.run_id ?? "",
    headline: `${row?.project_id ?? "n/a"} / ${row?.period_key ?? "n/a"}`,
    statusLabel: getRunStatusLabel(row?.status),
    stageLabel: row?.current_stage ?? "n/a",
    nodeLabel: row?.current_node ?? "n/a",
    activityLabel: row?.latest_activity_at ?? row?.completed_at ?? row?.created_at ?? "n/a",
    periodLabel:
      row?.period_start && row?.period_end ? `${row.period_start} -> ${row.period_end}` : "n/a",
    requesterLabel: row?.requester_id ?? "n/a",
    badges,
  };
}

export function getRunObservabilitySectionConfig(section) {
  return SECTION_CONFIGS.find((item) => item.key === section) ?? SECTION_CONFIGS[0];
}

export function getRunObservabilitySections() {
  return SECTION_CONFIGS.slice();
}

export function buildRunObservabilityPath(runId, section, cursor = null, limit = DEFAULT_RUN_LIST_LIMIT) {
  const config = getRunObservabilitySectionConfig(section);
  const params = new URLSearchParams();
  if (cursor) {
    params.set("cursor", cursor);
  }
  params.set("limit", String(Math.min(normalizePositiveInteger(limit, DEFAULT_RUN_LIST_LIMIT), MAX_RUN_LIST_LIMIT)));
  const suffix = params.toString();
  return `/api/v1/admin/runs/${encodeURIComponent(runId)}/${config.path}${suffix ? `?${suffix}` : ""}`;
}
