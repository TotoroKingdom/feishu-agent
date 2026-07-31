"use client";

import { useEffect, useState } from "react";

import {
  buildRunObservabilityPath,
  getRunObservabilitySectionConfig,
  getRunObservabilitySections,
  type ObservabilitySectionConfig,
  type ObservabilitySectionKey,
} from "@/lib/admin-observability";

type Props = {
  runId: string;
  requestId: string;
  isTerminal: boolean;
};

type SectionState = {
  status: "idle" | "loading" | "ready" | "error";
  error: string | null;
  items: Array<Record<string, unknown>>;
  nextCursor: string | null;
  hasMore: boolean;
  payload: Record<string, unknown> | null;
  requestId: string | null;
  loadedCursor: string | null;
};

type SectionStateMap = Record<ObservabilitySectionKey, SectionState>;

type SectionItemSummary = {
  title: string;
  status: string;
  meta: string[];
  details: string[];
  summaryBlocks?: Array<{
    label: string;
    value: unknown;
  }>;
};

function createSectionState(): SectionState {
  return {
    status: "idle",
    error: null,
    items: [],
    nextCursor: null,
    hasMore: false,
    payload: null,
    requestId: null,
    loadedCursor: null,
  };
}

function createInitialSectionState(): SectionStateMap {
  return Object.fromEntries(
    getRunObservabilitySections().map((section) => [section.key, createSectionState()]),
  ) as SectionStateMap;
}

function formatIso(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "Asia/Shanghai",
  }).format(parsed);
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value, null, 2);
}

function itemKey(section: ObservabilitySectionConfig, item: Record<string, unknown>, index: number): string {
  const id =
    item.id ??
    item.event_id ??
    item.operation_id ??
    item.claim_id ??
    item.evidence_id ??
    item.run_id ??
    item.created_at ??
    item.occurred_at;
  return `${section.key}-${String(id ?? index)}`;
}

function describeSectionItem(section: ObservabilitySectionConfig, item: Record<string, unknown>): SectionItemSummary {
  switch (section.key) {
    case "timeline":
      return {
        title: String(item.event_type ?? "event"),
        status: String(item.event_type ?? "event"),
        meta: [
          `event ${String(item.event_id ?? "n/a")}`,
          `at ${formatIso((item.occurred_at as string | null | undefined) ?? null)}`,
        ],
        details: [renderValue(item.summary)],
      };
    case "nodes":
      return {
        title: String(item.node_name ?? "node"),
        status: String(item.status ?? "unknown"),
        meta: [
          `attempt ${String(item.node_attempt ?? "n/a")}`,
          `duration ${String(item.duration_ms ?? 0)}ms`,
        ],
        details: [
          `checkpoint before ${String(item.checkpoint_before ?? "n/a")}`,
          `checkpoint after ${String(item.checkpoint_after ?? "n/a")}`,
        ],
        summaryBlocks: [
          { label: "Input", value: item.input_summary },
          { label: "Output", value: item.output_summary },
        ],
      };
    case "tools":
      return {
        title: String(item.tool_name ?? "tool"),
        status: String(item.status ?? "unknown"),
        meta: [
          `node ${String(item.node_execution_id ?? "n/a")}`,
          `attempt ${String(item.attempt ?? "n/a")}`,
        ],
        details: [
          `retryable ${String(Boolean(item.retryable))}`,
          `error ${String(item.error_code ?? item.error_class ?? "ok")}`,
        ],
        summaryBlocks: [
          { label: "Request", value: item.request_summary },
          { label: "Result", value: item.result_summary },
        ],
      };
    case "llm-executions":
      return {
        title: `${String(item.provider ?? "provider")} / ${String(item.model ?? "model")}`,
        status: String(item.status ?? "unknown"),
        meta: [
          `prompt ${String(item.prompt_type ?? "n/a")}`,
          `tokens ${String(item.total_tokens ?? "n/a")}`,
        ],
        details: [
          `schema valid ${String(Boolean(item.schema_valid))}`,
          `output ${String(item.output_ref ?? "n/a")}`,
        ],
      };
    case "diagnoses":
      return {
        title: String(item.problem_key ?? "diagnosis"),
        status: String(item.result ?? "unknown"),
        meta: [
          `severity ${String(item.severity ?? "n/a")}`,
          `attempt ${String(item.attempt ?? "n/a")}`,
        ],
        details: [
          `planned action ${String(item.planned_action ?? "n/a")}`,
          `next node ${String(item.next_node ?? "n/a")}`,
        ],
        summaryBlocks: [
          { label: "Observation", value: item.observation },
          { label: "Diagnosis", value: item.diagnosis },
          { label: "Scope", value: item.impact_scope },
        ],
      };
    case "approvals":
      return {
        title: String(item.approval_type ?? "approval"),
        status: String(item.status ?? "unknown"),
        meta: [
          `revision ${String(item.revision ?? "n/a")}`,
          `challenge ${String(item.challenge_id ?? "n/a")}`,
        ],
        details: [
          `decision ${String(item.decision ?? "n/a")}`,
          `actor ${String(item.actor_type ?? "n/a")} ${String(item.actor_id ?? "n/a")}`,
        ],
      };
    case "evidence":
      return {
        title: String(item.evidence_key ?? "evidence"),
        status: String(item.source_type ?? "unknown"),
        meta: [
          `source ${String(item.source_resource_id ?? "n/a")}`,
          `confidence ${String(item.confidence ?? "n/a")}`,
        ],
        details: [
          String(item.url ?? "n/a"),
          String(item.evidence_summary ?? "n/a"),
        ],
      };
    case "artifacts":
      return {
        title: String(item.artifact_type ?? "artifact"),
        status: String(item.status ?? "unknown"),
        meta: [
          `operation ${String(item.operation_id ?? "n/a")}`,
          `verified ${formatIso((item.verified_at as string | null | undefined) ?? null)}`,
        ],
        details: [String(item.url ?? "n/a"), String(item.external_id ?? "n/a")],
      };
    case "side-effects":
      return {
        title: String(item.operation_type ?? "operation"),
        status: String(item.status ?? "unknown"),
        meta: [
          `sequence ${String(item.sequence ?? "n/a")}`,
          `attempts ${String(item.attempt_count ?? "n/a")}`,
        ],
        details: [
          String(item.external_url ?? "n/a"),
          String(item.last_error_summary ?? "none"),
        ],
      };
    case "publish-plan":
      return {
        title: String(item.status ?? "publish plan"),
        status: String(item.status ?? "unknown"),
        meta: [
          `version ${String(item.version ?? "n/a")}`,
          `hash ${String(item.plan_hash ?? "n/a")}`,
        ],
        details: [
          `approved ${formatIso((item.approved_at as string | null | undefined) ?? null)}`,
          `invalidated ${formatIso((item.invalidated_at as string | null | undefined) ?? null)}`,
        ],
        summaryBlocks: [
          { label: "Plan", value: item.canonical_plan },
        ],
      };
    default:
      return {
        title: String(item.id ?? "item"),
        status: "unknown",
        meta: [],
        details: [renderValue(item)],
      };
  }
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

function SectionRow({
  section,
  item,
  index,
}: {
  section: ObservabilitySectionConfig;
  item: Record<string, unknown>;
  index: number;
}) {
  const summary = describeSectionItem(section, item);
  return (
    <div className="list-row" key={itemKey(section, item, index)}>
      <div>
        <div className="row-title">
          <strong>{summary.title}</strong>
          <span className="mini-pill">{summary.status}</span>
        </div>
        {summary.meta.map((text) => (
          <div className="row-metadata" key={text}>
            {text}
          </div>
        ))}
      </div>
      {summary.details.length > 0 ? (
        <div className="row-side">
          {summary.details.map((text) => (
            <span key={text}>{text}</span>
          ))}
        </div>
      ) : null}
      {summary.summaryBlocks ? (
        <div className="summary-block">
          {summary.summaryBlocks.map((block) => (
            <div key={block.label}>
              <span className="summary-label">{block.label}</span>
              <pre>{renderValue(block.value)}</pre>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function RunObservabilityPanel({ runId, requestId, isTerminal }: Props) {
  const sections = getRunObservabilitySections();
  const [activeSection, setActiveSection] = useState<ObservabilitySectionKey>("timeline");
  const [sectionState, setSectionState] = useState<SectionStateMap>(createInitialSectionState);

  async function loadSection(section: ObservabilitySectionKey, cursor: string | null = null, append = false) {
    const config = getRunObservabilitySectionConfig(section);
    setSectionState((current) => ({
      ...current,
      [section]: {
        ...current[section],
        status: "loading",
        error: null,
      },
    }));

    try {
      const response = await fetch(buildRunObservabilityPath(runId, section, cursor), {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Failed to load ${config.label} (${response.status})`);
      }

      const payload = (await response.json()) as {
        data?: Record<string, unknown> | Array<Record<string, unknown>>;
        meta?: { request_id?: string };
      };
      const data = payload.data ?? {};

      if (config.kind === "single") {
        setSectionState((current) => ({
          ...current,
          [section]: {
            ...current[section],
            status: "ready",
            error: null,
            payload: data as Record<string, unknown>,
            items: [],
            nextCursor: null,
            hasMore: false,
            loadedCursor: null,
            requestId: payload.meta?.request_id ?? null,
          },
        }));
        return;
      }

      const page = data as {
        items?: Array<Record<string, unknown>>;
        next_cursor?: string | null;
        has_more?: boolean;
      };
      const items = Array.isArray(page.items) ? page.items : [];

      setSectionState((current) => {
        const previous = current[section];
        return {
          ...current,
          [section]: {
            ...previous,
            status: "ready",
            error: null,
            items: append ? [...previous.items, ...items] : items,
            nextCursor: page.next_cursor ?? null,
            hasMore: Boolean(page.has_more),
            payload: null,
            loadedCursor: cursor,
            requestId: payload.meta?.request_id ?? null,
          },
        };
      });
    } catch (error) {
      setSectionState((current) => ({
        ...current,
        [section]: {
          ...current[section],
          status: "error",
          error: error instanceof Error ? error.message : `Failed to load ${config.label}`,
        },
      }));
    }
  }

  useEffect(() => {
    const current = sectionState[activeSection];
    if (current.status !== "idle" || current.loadedCursor !== null) {
      return;
    }
    void loadSection(activeSection);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSection, runId]);

  const activeConfig = getRunObservabilitySectionConfig(activeSection);
  const activeState = sectionState[activeSection];
  const liveLabel = isTerminal ? "terminal" : "live";
  const retrySection = () => {
    if (activeConfig.kind === "page" && activeState.items.length > 0 && activeState.nextCursor) {
      void loadSection(activeSection, activeState.nextCursor, true);
      return;
    }
    void loadSection(activeSection);
  };

  return (
    <section className="panel observability-panel">
      <div className="panel-head">
        <div>
          <p className="section-label">Observability</p>
          <h2>Timeline and traces</h2>
        </div>
        <span className="mono-chip">
          {liveLabel} | request {requestId || "n/a"}
        </span>
      </div>

      <div className="tab-strip" role="tablist" aria-label="Run observability panels">
        {sections.map((section) => {
          const state = sectionState[section.key];
          const count = section.kind === "single" ? (state.payload ? 1 : 0) : state.items.length;
          return (
            <button
              key={section.key}
              type="button"
              role="tab"
              aria-selected={activeSection === section.key}
              className={activeSection === section.key ? "tab-button tab-button-active" : "tab-button"}
              onClick={() => setActiveSection(section.key)}
            >
              <span>{section.label}</span>
              <span className="tab-count">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="panel-head panel-head-spaced">
        <div>
          <p className="section-label">{activeConfig.label}</p>
          <h3>{activeConfig.kind === "single" ? "Single record" : "Paged trace"}</h3>
        </div>
        <div className="hero-meta">
          {activeConfig.kind === "page" ? (
            <span className="meta-chip">
              cursor {activeState.loadedCursor ?? "start"} {activeState.hasMore ? "-> more" : "end"}
            </span>
          ) : null}
          {activeState.requestId ? <span className="meta-chip">request {activeState.requestId}</span> : null}
        </div>
      </div>

      {activeState.status === "loading" ? <EmptyState text={`Loading ${activeConfig.label.toLowerCase()}...`} /> : null}
      {activeState.status === "error" ? (
        <section className="inline-alert inline-alert-warning">
          <div>{activeState.error ?? `Unable to load ${activeConfig.label}`}</div>
          <div className="panel-actions">
            <button className="secondary-button" type="button" onClick={retrySection}>
              Retry
            </button>
          </div>
        </section>
      ) : null}

      {activeState.status === "ready" && activeConfig.kind === "page" ? (
        <div className="stack">
          {activeState.items.length > 0 ? (
            activeState.items.map((item, index) => (
              <SectionRow key={itemKey(activeConfig, item, index)} section={activeConfig} item={item} index={index} />
            ))
          ) : (
            <EmptyState text={`No ${activeConfig.label.toLowerCase()} yet`} />
          )}
          <div className="panel-actions">
            <button
              className="secondary-button"
              type="button"
              disabled={!activeState.hasMore}
              onClick={() => {
                if (activeState.nextCursor) {
                  void loadSection(activeSection, activeState.nextCursor, true);
                }
              }}
            >
              {activeState.hasMore ? "Load more" : "No more rows"}
            </button>
          </div>
        </div>
      ) : null}

      {activeState.status === "ready" && activeConfig.kind === "single" ? (
        activeState.payload ? (
          <div className="single-record">
            <div className="row-title">
              <strong>{String(activeState.payload.status ?? activeConfig.label)}</strong>
              <span className="mini-pill">{String(activeState.payload.status ?? "unknown")}</span>
            </div>
            <div className="detail-grid detail-grid-compact">
              {Object.entries(activeState.payload)
                .slice(0, 6)
                .map(([key, value]) => (
                  <div className="detail-row" key={key}>
                    <span>{key}</span>
                    <strong>{renderValue(value)}</strong>
                  </div>
                ))}
            </div>
            <div className="summary-block">
              <div>
                <span className="summary-label">Raw payload</span>
                <pre>{renderValue(activeState.payload)}</pre>
              </div>
            </div>
          </div>
        ) : (
          <EmptyState text={`No ${activeConfig.label.toLowerCase()} yet`} />
        )
      ) : null}
    </section>
  );
}
