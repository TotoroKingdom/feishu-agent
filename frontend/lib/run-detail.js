const TERMINAL_RUN_STATUSES = new Set(["completed", "blocked", "rejected", "cancelled"]);

const STATUS_LABELS = {
  created: "Created",
  waiting: "Waiting",
  completed: "Completed",
  blocked: "Blocked",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export function isTerminalRunStatus(status) {
  return TERMINAL_RUN_STATUSES.has(String(status ?? "").toLowerCase());
}

export function getRunStatusLabel(status) {
  const normalized = String(status ?? "").toLowerCase();
  return STATUS_LABELS[normalized] ?? String(status ?? "unknown");
}

export function summarizeRunDetail(detail) {
  const terminal = isTerminalRunStatus(detail.status) || Boolean(detail.is_terminal);
  const pollingIntervalMs = Number(detail.polling_interval_ms ?? 5000);
  const shouldPoll = Boolean(detail.should_poll) && !terminal;

  return {
    headline: `${detail.project_id} / ${detail.period_key}`,
    statusLabel: getRunStatusLabel(detail.status),
    stageLabel: detail.current_stage,
    nodeLabel: detail.current_node ?? "unknown",
    pollingLabel: shouldPoll
      ? `Auto refresh every ${Math.round(pollingIntervalMs / 1000)}s`
      : "Polling paused",
    isTerminal: terminal,
    shouldPoll,
    pollingIntervalMs,
    approvalsCount: detail.approvals?.length ?? 0,
    toolsCount: detail.tools?.length ?? 0,
    artifactsCount: detail.artifacts?.length ?? 0,
    sideEffectsCount: detail.side_effects?.length ?? 0,
  };
}
