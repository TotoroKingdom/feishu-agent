export interface RunApprovalSummary {
  approval_type: string;
  status: string;
  revision: number;
  challenge_id: string;
  requested_from: string[];
  decision?: string | null;
  actor_id?: string | null;
  actor_type?: string | null;
  decided_at?: string | null;
  request_payload_hash: string;
  plan_hash?: string | null;
}

export interface RunToolSummary {
  node_execution_id: string;
  tool_name: string;
  status: string;
  attempt: number;
  duration_ms?: number | null;
  data_ref?: string | null;
  retryable: boolean;
  error_code?: string | null;
  error_class?: string | null;
  request_summary: Record<string, unknown>;
  result_summary: Record<string, unknown>;
}

export interface RunArtifactSummary {
  artifact_type: string;
  operation_id: string;
  external_id?: string | null;
  url?: string | null;
  status: string;
  verified_at?: string | null;
}

export interface RunSideEffectSummary {
  operation_id: string;
  sequence: number;
  operation_type: string;
  status: string;
  attempt_count: number;
  external_resource_id?: string | null;
  external_url?: string | null;
  verification_status?: string | null;
  last_error_class?: string | null;
  last_error_summary?: string | null;
}

export interface RunRefs {
  report_version_ref?: string | null;
  publish_plan_ref?: string | null;
  approved_publish_plan_ref?: string | null;
  artifact_refs: string[];
  operation_refs: string[];
}

export interface RunTimestampSummary {
  created_at: string;
  latest_activity_at?: string | null;
  completed_at?: string | null;
}

export interface RunDetailView {
  run_id: string;
  project_id: string;
  period_key: string;
  period_start: string;
  period_end: string;
  status: string;
  current_stage: string;
  current_node?: string | null;
  graph_version: string;
  requester_id: string;
  approval_status: string;
  approval_revision: number;
  error_code?: string | null;
  error_summary?: string | null;
  is_terminal: boolean;
  should_poll: boolean;
  polling_interval_ms: number;
  timestamps: RunTimestampSummary;
  approvals: RunApprovalSummary[];
  tools: RunToolSummary[];
  artifacts: RunArtifactSummary[];
  side_effects: RunSideEffectSummary[];
  refs: RunRefs;
}

export interface RunDetailEnvelope {
  data: RunDetailView;
  meta: {
    request_id: string;
  };
}

export interface RunDetailSummary {
  headline: string;
  statusLabel: string;
  stageLabel: string;
  nodeLabel: string;
  pollingLabel: string;
  isTerminal: boolean;
  shouldPoll: boolean;
  pollingIntervalMs: number;
  approvalsCount: number;
  toolsCount: number;
  artifactsCount: number;
  sideEffectsCount: number;
}

export declare function isTerminalRunStatus(status: string | null | undefined): boolean;
export declare function getRunStatusLabel(status: string | null | undefined): string;
export declare function summarizeRunDetail(detail: RunDetailView): RunDetailSummary;

