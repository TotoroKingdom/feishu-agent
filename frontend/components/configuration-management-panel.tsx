"use client";

import { useEffect, useMemo, useState } from "react";

import {
  buildConfigurationConfirmation,
  buildCredentialDraftSummary,
  clearCredentialDraft,
  computeCanonicalJsonHash,
  summarizeFeishuMappingConfiguration,
  summarizeRepositoryConfiguration,
  type ConfigurationConfirmation,
  type CredentialDraft,
  type CredentialDraftSummary,
  type FeishuFieldDraft,
  type FeishuMappingDraft,
  type FeishuMappingSummary,
  type FeishuResourceConfig,
  type RepositoryConfig,
  type RepositoryConfigurationSummary,
} from "@/lib/configuration";

export type ProjectConfig = {
  id: string;
  name: string;
  description: string | null;
  timezone: string;
  default_period_rule: Record<string, unknown>;
  default_prompt_version_id: string | null;
  revision: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ModelConfig = {
  id: string;
  scope: string;
  base_url: string | null;
  model: string;
  temperature: number;
  timeout_seconds: number;
  max_retries: number;
  stream: boolean;
  revision: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PromptVersion = {
  id: string;
  prompt_type: string;
  version: number;
  content: string;
  content_hash: string;
  status: string;
  model_constraints: Record<string, unknown>;
  created_by: string;
  created_at?: string | null;
};

export type ConnectivityJob = {
  id: string;
  job_type: string;
  status: string;
  result_summary: Record<string, unknown>;
  error_code: string | null;
  error_summary: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
};

export type ConfigurationSnapshot = {
  project: ProjectConfig;
  repositories: RepositoryConfig[];
  feishuResources: FeishuResourceConfig[];
  modelConfig: ModelConfig;
  prompts: PromptVersion[];
};

type RepositoryDraft = {
  id: string;
  owner: string;
  repo: string;
  repository_type: string;
  weight: string;
  enabled: boolean;
  default_branch: string;
  revision: string;
};

type ResourceDraft = {
  id: string;
  resource_type: string;
  external_id: string;
  name: string;
  enabled: boolean;
  schema_hash: string;
  revision: string;
};

type PromptDraft = {
  prompt_type: string;
  content: string;
  created_by: string;
  status: string;
};

type SchemaDraft = {
  jsonText: string;
};

type PendingReview = {
  title: string;
  review: ConfigurationConfirmation;
  confirmLabel: string;
  apply: () => Promise<void>;
};

type AuditEntry = {
  title: string;
  kind: string;
  requestHash: string;
  revisionLabel: string;
  timestamp: string;
  review: ConfigurationConfirmation;
};

const EMPTY_REPOSITORY_DRAFT: RepositoryDraft = {
  id: "",
  owner: "",
  repo: "",
  repository_type: "github",
  weight: "100",
  enabled: true,
  default_branch: "main",
  revision: "1",
};

const EMPTY_RESOURCE_DRAFT: ResourceDraft = {
  id: "",
  resource_type: "bitable",
  external_id: "",
  name: "",
  enabled: true,
  schema_hash: "",
  revision: "1",
};

const EMPTY_PROMPT_DRAFT: PromptDraft = {
  prompt_type: "report",
  content: "",
  created_by: "admin",
  status: "draft",
};

const EMPTY_SCHEMA_DRAFT: SchemaDraft = {
  jsonText: "",
};

const EMPTY_CREDENTIAL_DRAFT: CredentialDraft = {
  credentialType: "github_pat",
  label: "primary",
  secret: "",
  status: "draft",
  fingerprintSuffix: "",
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Shanghai",
  }).format(parsed);
}

function formatJson(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: { message?: string } | string };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    return payload.detail?.message ?? `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return (await response.json()) as T;
}

function blankRepositoryDraft(repository?: RepositoryConfig | null): RepositoryDraft {
  return {
    id: repository?.id ?? "",
    owner: repository?.owner ?? "",
    repo: repository?.repo ?? "",
    repository_type: repository?.repository_type ?? repository?.provider ?? "github",
    weight: String(repository?.weight ?? 100),
    enabled: Boolean(repository?.enabled ?? true),
    default_branch: repository?.default_branch ?? "main",
    revision: String(repository?.revision ?? 1),
  };
}

function blankResourceDraft(resource?: FeishuResourceConfig | null): ResourceDraft {
  return {
    id: resource?.id ?? "",
    resource_type: resource?.resource_type ?? "bitable",
    external_id: resource?.external_id ?? "",
    name: resource?.name ?? "",
    enabled: Boolean(resource?.enabled ?? true),
    schema_hash: resource?.schema_hash ?? "",
    revision: String(resource?.revision ?? 1),
  };
}

function toProjectPayload(project: ProjectConfig, defaultPeriodRuleText: string): Record<string, unknown> {
  let defaultPeriodRule: Record<string, unknown> = {};
  try {
    defaultPeriodRule = JSON.parse(defaultPeriodRuleText || "{}") as Record<string, unknown>;
  } catch {
    throw new Error("Default period rule must be valid JSON");
  }

  return {
    name: project.name.trim(),
    description: project.description?.trim() || null,
    timezone: project.timezone.trim(),
    default_period_rule: defaultPeriodRule,
    default_prompt_version_id: project.default_prompt_version_id || null,
    revision: project.revision,
  };
}

function toRepositoryPayload(draft: RepositoryDraft): Record<string, unknown> {
  const owner = draft.owner.trim();
  const repo = draft.repo.trim();
  if (!owner || !repo) {
    throw new Error("Repository owner and repo are required");
  }

  return {
    owner,
    repo,
    repository_type: draft.repository_type.trim() || "github",
    weight: Number(draft.weight),
    enabled: draft.enabled,
    default_branch: draft.default_branch.trim() || null,
    revision: Number(draft.revision),
  };
}

function toResourcePayload(draft: ResourceDraft): Record<string, unknown> {
  if (!draft.resource_type.trim() || !draft.external_id.trim()) {
    throw new Error("Feishu resource type and external id are required");
  }

  return {
    resource_type: draft.resource_type.trim(),
    external_id: draft.external_id.trim(),
    name: draft.name.trim() || null,
    enabled: draft.enabled,
    schema_hash: draft.schema_hash.trim() || null,
    revision: Number(draft.revision),
  };
}

function createMappingRow(initial?: FeishuFieldDraft): FeishuFieldDraft {
  return {
    logicalField: initial?.logicalField ?? "",
    externalFieldId: initial?.externalFieldId ?? "",
    externalFieldName: initial?.externalFieldName ?? "",
    externalFieldType: initial?.externalFieldType ?? "text",
    converter: initial?.converter ?? "text",
    requiredLevel: initial?.requiredLevel ?? "optional",
    mappingOptions: initial?.mappingOptions ?? {},
    enabled: initial?.enabled ?? true,
  };
}

function cloneMappingRows(rows: FeishuFieldDraft[]): FeishuFieldDraft[] {
  return rows.map((row) => ({ ...row, mappingOptions: { ...(row.mappingOptions ?? {}) } }));
}

function addAuditEntry(title: string, review: ConfigurationConfirmation): AuditEntry {
  return {
    title,
    kind: review.kind,
    requestHash: review.requestHash,
    revisionLabel: review.revisionLabel,
    timestamp: new Date().toISOString(),
    review,
  };
}

function badgeClass(tone: string): string {
  switch (tone) {
    case "success":
      return "mini-pill mini-pill-success";
    case "warning":
      return "mini-pill mini-pill-warning";
    case "danger":
      return "mini-pill mini-pill-danger";
    default:
      return "mini-pill";
  }
}

function Field({
  label,
  children,
  span = 1,
}: {
  label: string;
  children: React.ReactNode;
  span?: 1 | 2;
}) {
  return (
    <label className={`field field-span-${span}`}>
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-card">
      <span className="summary-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MappingRowEditor({
  row,
  onChange,
  onRemove,
}: {
  row: FeishuFieldDraft;
  onChange: (row: FeishuFieldDraft) => void;
  onRemove: () => void;
}) {
  return (
    <article className="mapping-row">
      <div className="form-grid form-grid-3">
        <input className="text-input" placeholder="logical field" value={row.logicalField} onChange={(event) => onChange({ ...row, logicalField: event.target.value })} />
        <input className="text-input" placeholder="external field id" value={row.externalFieldId} onChange={(event) => onChange({ ...row, externalFieldId: event.target.value })} />
        <input className="text-input" placeholder="external field name" value={row.externalFieldName ?? ""} onChange={(event) => onChange({ ...row, externalFieldName: event.target.value })} />
        <input className="text-input" placeholder="external field type" value={row.externalFieldType ?? ""} onChange={(event) => onChange({ ...row, externalFieldType: event.target.value })} />
        <input className="text-input" placeholder="converter" value={row.converter ?? ""} onChange={(event) => onChange({ ...row, converter: event.target.value })} />
        <select className="text-input" value={row.requiredLevel ?? "optional"} onChange={(event) => onChange({ ...row, requiredLevel: event.target.value })}>
          <option value="critical">critical</option>
          <option value="required">required</option>
          <option value="optional">optional</option>
        </select>
      </div>
      <div className="row-actions">
        <label className="toggle-row">
          <input type="checkbox" checked={row.enabled !== false} onChange={(event) => onChange({ ...row, enabled: event.target.checked })} />
          <span>Enabled</span>
        </label>
        <button className="text-button text-button-danger" type="button" onClick={onRemove}>
          Remove
        </button>
      </div>
    </article>
  );
}

export function ConfigurationManagementPanel({ initialState }: { initialState: ConfigurationSnapshot }) {
  const [project, setProject] = useState<ProjectConfig>(initialState.project);
  const [defaultPeriodRuleText, setDefaultPeriodRuleText] = useState(
    JSON.stringify(initialState.project.default_period_rule ?? {}, null, 2),
  );
  const [repositories, setRepositories] = useState<RepositoryConfig[]>(initialState.repositories);
  const [repositoryDraft, setRepositoryDraft] = useState<RepositoryDraft>(blankRepositoryDraft());
  const [selectedRepositoryId, setSelectedRepositoryId] = useState<string | null>(null);
  const [resources, setResources] = useState<FeishuResourceConfig[]>(initialState.feishuResources);
  const [resourceDraft, setResourceDraft] = useState<ResourceDraft>(blankResourceDraft());
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(initialState.feishuResources[0]?.id ?? null);
  const [schemaDraft, setSchemaDraft] = useState<SchemaDraft>(EMPTY_SCHEMA_DRAFT);
  const [mappingRows, setMappingRows] = useState<FeishuFieldDraft[]>([createMappingRow()]);
  const [modelConfig, setModelConfig] = useState<ModelConfig>(initialState.modelConfig);
  const [promptDraft, setPromptDraft] = useState<PromptDraft>(EMPTY_PROMPT_DRAFT);
  const [prompts, setPrompts] = useState<PromptVersion[]>(initialState.prompts);
  const [credentialDraft, setCredentialDraft] = useState<CredentialDraft>(EMPTY_CREDENTIAL_DRAFT);
  const [credentialSummary, setCredentialSummary] = useState<CredentialDraftSummary | null>(null);
  const [connectivityJob, setConnectivityJob] = useState<ConnectivityJob | null>(null);
  const [pendingReview, setPendingReview] = useState<PendingReview | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const repositorySummary: RepositoryConfigurationSummary = useMemo(
    () => summarizeRepositoryConfiguration(repositories),
    [repositories],
  );

  const selectedResource = useMemo(
    () => resources.find((resource) => resource.id === selectedResourceId) ?? resources[0] ?? null,
    [resources, selectedResourceId],
  );

  const mappingSummary: FeishuMappingSummary = useMemo(
    () =>
      summarizeFeishuMappingConfiguration(selectedResource, {
        schemaHash: resourceDraft.schema_hash || selectedResource?.schema_hash || "",
        requiredLogicalFields: mappingRows
          .filter((row) => row.requiredLevel === "critical" || row.requiredLevel === "required")
          .map((row) => row.logicalField),
        fields: cloneMappingRows(mappingRows),
      }),
    [mappingRows, resourceDraft.schema_hash, selectedResource],
  );

  const activePrompts = useMemo(
    () => prompts.filter((prompt) => prompt.prompt_type === promptDraft.prompt_type),
    [prompts, promptDraft.prompt_type],
  );

  useEffect(() => {
    if (!connectivityJob || connectivityJob.status !== "running") {
      return;
    }

    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const response = await requestJson<{ data: ConnectivityJob }>(
          `/api/v1/admin/connectivity-jobs/${encodeURIComponent(connectivityJob.id)}`,
        );
        if (cancelled) {
          return;
        }
        setConnectivityJob(response.data);
        if (response.data.status !== "running") {
          window.clearInterval(timer);
        }
      } catch (jobError) {
        if (!cancelled) {
          setError(jobError instanceof Error ? jobError.message : "Connectivity check failed");
          window.clearInterval(timer);
        }
      }
    }, 3500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [connectivityJob]);

  async function openReview(
    title: string,
    kind: string,
    before: Record<string, unknown>,
    after: Record<string, unknown>,
    confirmLabel: string,
    apply: () => Promise<void>,
  ) {
    setError(null);
    setNotice(null);
    const review = await buildConfigurationConfirmation({ kind, before, after });
    setPendingReview({ title, review, confirmLabel, apply });
  }

  async function confirmReview() {
    if (!pendingReview) {
      return;
    }

    setReviewBusy(true);
    try {
      await pendingReview.apply();
      setAuditLog((current) => [addAuditEntry(pendingReview.title, pendingReview.review), ...current].slice(0, 10));
      setNotice(`${pendingReview.title} saved`);
      setPendingReview(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Save failed");
    } finally {
      setReviewBusy(false);
    }
  }

  async function handleProjectSave() {
    let parsedRule: Record<string, unknown>;
    try {
      parsedRule = JSON.parse(defaultPeriodRuleText || "{}") as Record<string, unknown>;
    } catch {
      setError("Default period rule must be valid JSON");
      return;
    }

    const nextProject = { ...project, default_period_rule: parsedRule };
    await openReview("Project configuration", "project", project, nextProject, "Confirm project update", async () => {
      const response = await requestJson<{ data: ProjectConfig }>("/api/v1/admin/project", {
        method: "PUT",
        body: JSON.stringify(toProjectPayload(nextProject, defaultPeriodRuleText)),
      });
      setProject(response.data);
      setDefaultPeriodRuleText(JSON.stringify(response.data.default_period_rule ?? {}, null, 2));
    });
  }

  async function handleRepositorySave() {
    const payload = toRepositoryPayload(repositoryDraft);
    const existing = repositories.find((repository) => repository.id === repositoryDraft.id);
    const nextRepository = {
      id: repositoryDraft.id,
      project_id: project.id,
      owner: repositoryDraft.owner.trim(),
      repo: repositoryDraft.repo.trim(),
      repository_type: repositoryDraft.repository_type.trim() || "github",
      external_id: `${repositoryDraft.owner.trim()}/${repositoryDraft.repo.trim()}`,
      provider: repositoryDraft.repository_type.trim() || "github",
      weight: Number(repositoryDraft.weight),
      enabled: repositoryDraft.enabled,
      default_branch: repositoryDraft.default_branch.trim() || null,
      last_connectivity_status: existing?.last_connectivity_status ?? null,
      last_connectivity_at: existing?.last_connectivity_at ?? null,
      revision: Number(repositoryDraft.revision),
      updated_at: existing?.updated_at ?? null,
    };

    await openReview(
      existing ? "Repository update" : "Repository create",
      existing ? "repository_update" : "repository_create",
      existing ?? {},
      nextRepository,
      existing ? "Confirm repository update" : "Confirm repository create",
      async () => {
        const response = await requestJson<{ data: RepositoryConfig }>(
          existing ? `/api/v1/admin/project/repositories/${encodeURIComponent(repositoryDraft.id)}` : "/api/v1/admin/project/repositories",
          {
            method: existing ? "PATCH" : "POST",
            body: JSON.stringify(payload),
          },
        );
        const saved = response.data;
        setRepositories((current) =>
          existing ? current.map((row) => (row.id === saved.id ? saved : row)) : [saved, ...current],
        );
        setRepositoryDraft(blankRepositoryDraft(saved));
        setSelectedRepositoryId(saved.id);
      },
    );
  }

  async function handleRepositoryDisable(repository: RepositoryConfig) {
    await openReview(
      "Repository disable",
      "repository_delete",
      repository,
      { ...repository, enabled: false },
      "Confirm disable",
      async () => {
        const response = await requestJson<{ data: RepositoryConfig }>(
          `/api/v1/admin/project/repositories/${encodeURIComponent(repository.id)}`,
          { method: "DELETE" },
        );
        const saved = response.data;
        setRepositories((current) => current.map((row) => (row.id === saved.id ? saved : row)));
        if (repositoryDraft.id === repository.id) {
          setRepositoryDraft(blankRepositoryDraft(saved));
        }
      },
    );
  }

  async function handleRepositoryConnectivity(repository: RepositoryConfig) {
    try {
      const response = await requestJson<{ data: Record<string, unknown> }>(
        `/api/v1/admin/project/repositories/${encodeURIComponent(repository.id)}/connectivity-test`,
        { method: "POST" },
      );
      const requestHash = `${repository.id}:${Date.now()}`;
      setNotice(`Repository ${repository.external_id ?? repository.id} connectivity refreshed`);
      setAuditLog((current) => [
        {
          title: "Repository connectivity",
          kind: "repository_connectivity",
          requestHash,
          revisionLabel: String(response.data.status ?? "unknown"),
          timestamp: new Date().toISOString(),
          review: {
            kind: "repository_connectivity",
            requestHash,
            before: { status: repository.last_connectivity_status ?? "unknown" },
            after: { status: response.data.status ?? "unknown" },
            changeSummary: [
              {
                field: "status",
                before: String(repository.last_connectivity_status ?? "unknown"),
                after: String(response.data.status ?? "unknown"),
              },
            ],
            canSubmit: true,
            requiresFreshRevision: false,
            revisionLabel: String(response.data.status ?? "unknown"),
            riskFlags: [],
          },
        },
        ...current,
      ].slice(0, 10));
    } catch (connectivityError) {
      setError(connectivityError instanceof Error ? connectivityError.message : "Connectivity test failed");
    }
  }

  async function handleResourceSave() {
    const payload = toResourcePayload(resourceDraft);
    const existing = resources.find((resource) => resource.id === resourceDraft.id);
    const nextResource = {
      id: resourceDraft.id,
      project_id: project.id,
      resource_type: resourceDraft.resource_type.trim(),
      external_id: resourceDraft.external_id.trim(),
      name: resourceDraft.name.trim() || null,
      schema_hash: resourceDraft.schema_hash.trim() || null,
      enabled: resourceDraft.enabled,
      revision: Number(resourceDraft.revision),
      last_connectivity_status: existing?.last_connectivity_status ?? null,
      last_connectivity_at: existing?.last_connectivity_at ?? null,
      updated_at: existing?.updated_at ?? null,
    };

    await openReview(
      existing ? "Feishu resource update" : "Feishu resource create",
      existing ? "feishu_resource_update" : "feishu_resource_create",
      existing ?? {},
      nextResource,
      existing ? "Confirm resource update" : "Confirm resource create",
      async () => {
        const response = await requestJson<{ data: FeishuResourceConfig }>(
          existing ? `/api/v1/admin/project/feishu-resources/${encodeURIComponent(resourceDraft.id)}` : "/api/v1/admin/project/feishu-resources",
          {
            method: existing ? "PATCH" : "POST",
            body: JSON.stringify(payload),
          },
        );
        const saved = response.data;
        setResources((current) => (existing ? current.map((row) => (row.id === saved.id ? saved : row)) : [saved, ...current]));
        setResourceDraft(blankResourceDraft(saved));
        setSelectedResourceId(saved.id ?? null);
      },
    );
  }

  async function handleSchemaCompute() {
    try {
      const fields = JSON.parse(schemaDraft.jsonText || "[]") as Array<Record<string, unknown>>;
      const schemaHash = await computeCanonicalJsonHash(fields);
      setResourceDraft((current) => ({ ...current, schema_hash: schemaHash }));
      setNotice(`Schema hash computed: ${schemaHash.slice(0, 8)}...`);
    } catch {
      setError("Schema preview must be valid JSON array");
    }
  }

  async function handleSchemaSave() {
    if (!selectedResource) {
      setError("Select a Feishu resource first");
      return;
    }

    let fields: Array<Record<string, unknown>>;
    try {
      fields = JSON.parse(schemaDraft.jsonText || "[]") as Array<Record<string, unknown>>;
    } catch {
      setError("Schema preview must be valid JSON array");
      return;
    }

    const computedHash = resourceDraft.schema_hash.trim() || (await computeCanonicalJsonHash(fields));
    const before = { schema_hash: selectedResource.schema_hash ?? null, revision: selectedResource.revision };
    const after = { schema_hash: computedHash, revision: Number(resourceDraft.revision) };

    await openReview("Feishu schema update", "feishu_schema", before, after, "Confirm schema update", async () => {
      const response = await requestJson<{ data: FeishuResourceConfig }>(
        `/api/v1/admin/project/feishu-resources/${encodeURIComponent(selectedResource.id as string)}/schema`,
        {
          method: "POST",
          body: JSON.stringify({
            schema_hash: computedHash,
            revision: Number(resourceDraft.revision),
            fields,
          }),
        },
      );
      const saved = response.data;
      setResources((current) => current.map((row) => (row.id === saved.id ? saved : row)));
      setResourceDraft((current) => ({ ...current, schema_hash: saved.schema_hash ?? "", revision: String(saved.revision ?? 1) }));
    });
  }

  async function handleMappingSave() {
    if (!selectedResource) {
      setError("Select a Feishu resource first");
      return;
    }

    const payload = {
      schema_hash: resourceDraft.schema_hash.trim() || selectedResource.schema_hash || "",
      revision: Number(resourceDraft.revision),
      mappings: mappingRows.map((row) => ({
        logical_field: row.logicalField.trim(),
        external_field_id: row.externalFieldId.trim(),
        external_field_name: row.externalFieldName?.trim() || null,
        external_field_type: row.externalFieldType?.trim() || null,
        converter: row.converter?.trim() || null,
        required_level: row.requiredLevel,
        mapping_options: row.mappingOptions ?? {},
        enabled: Boolean(row.enabled),
      })),
    };

    await openReview(
      "Feishu mappings update",
      "feishu_mappings",
      {
        resource_id: selectedResource.id,
        schema_hash: selectedResource.schema_hash,
        revision: selectedResource.revision,
      },
      payload as Record<string, unknown>,
      "Confirm mappings update",
      async () => {
        const response = await requestJson<{ data: Record<string, unknown> }>(
          `/api/v1/admin/project/feishu-resources/${encodeURIComponent(selectedResource.id as string)}/field-mappings`,
          {
            method: "PUT",
            body: JSON.stringify(payload),
          },
        );
        const nextRevision = Number(response.data.revision ?? Number(resourceDraft.revision) + 1);
        setResources((current) =>
          current.map((row) =>
            row.id === selectedResource.id
              ? {
                  ...row,
                  revision: nextRevision,
                  schema_hash: payload.schema_hash,
                }
              : row,
          ),
        );
        setResourceDraft((current) => ({ ...current, revision: String(nextRevision) }));
      },
    );
  }

  async function handleResourceConnectivity(resource: FeishuResourceConfig) {
    try {
      const response = await requestJson<{ data: Record<string, unknown> }>(
        `/api/v1/admin/project/feishu-resources/${encodeURIComponent(resource.id as string)}/connectivity-test`,
        { method: "POST" },
      );
      setNotice(`Feishu resource ${resource.external_id ?? resource.id} connectivity refreshed`);
      setResources((current) =>
        current.map((row) =>
          row.id === resource.id
            ? {
                ...row,
                last_connectivity_status: String(response.data.status ?? "unknown"),
              }
            : row,
        ),
      );
    } catch (connectivityError) {
      setError(connectivityError instanceof Error ? connectivityError.message : "Connectivity test failed");
    }
  }

  async function handleModelSave() {
    const nextModel = {
      ...modelConfig,
      temperature: Number(modelConfig.temperature),
      timeout_seconds: Number(modelConfig.timeout_seconds),
      max_retries: Number(modelConfig.max_retries),
      stream: Boolean(modelConfig.stream),
    };

    await openReview("Model configuration", "model_config", modelConfig, nextModel, "Confirm model config", async () => {
      const response = await requestJson<{ data: ModelConfig }>("/api/v1/admin/model-config", {
        method: "PATCH",
        body: JSON.stringify({
          base_url: nextModel.base_url,
          model: nextModel.model,
          temperature: nextModel.temperature,
          timeout_seconds: nextModel.timeout_seconds,
          max_retries: nextModel.max_retries,
          stream: nextModel.stream,
          revision: nextModel.revision,
        }),
      });
      setModelConfig(response.data);
    });
  }

  async function handlePromptCreate() {
    const payload = {
      prompt_type: promptDraft.prompt_type,
      content: promptDraft.content,
      status: promptDraft.status,
      created_by: promptDraft.created_by,
      model_constraints: {},
    };

    await openReview("Prompt create", "prompt_create", { prompt_type: promptDraft.prompt_type }, payload, "Confirm prompt create", async () => {
      const response = await requestJson<{ data: PromptVersion }>("/api/v1/admin/prompts", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setPrompts((current) => [response.data, ...current]);
      setPromptDraft(EMPTY_PROMPT_DRAFT);
    });
  }

  async function handlePromptActivate(prompt: PromptVersion) {
    await openReview(
      "Prompt activate",
      "prompt_activate",
      { prompt_version_id: prompt.id, status: prompt.status },
      { prompt_version_id: prompt.id, status: "active" },
      "Confirm prompt activate",
      async () => {
        const response = await requestJson<{ data: PromptVersion }>(
          `/api/v1/admin/prompts/${encodeURIComponent(prompt.id)}/activate`,
          { method: "POST" },
        );
        setPrompts((current) =>
          current.map((row) =>
            row.prompt_type === response.data.prompt_type
              ? { ...row, status: row.id === response.data.id ? response.data.status : "retired" }
              : row,
          ),
        );
        setProject((current) => ({ ...current, default_prompt_version_id: response.data.id }));
      },
    );
  }

  async function handleConnectivityRun() {
    const response = await requestJson<{ data: ConnectivityJob }>("/api/v1/admin/project/connectivity-test", {
      method: "POST",
    });
    setConnectivityJob(response.data);
    setNotice("Connectivity check started");
  }

  async function handleCredentialStage() {
    const summary = await buildCredentialDraftSummary(credentialDraft);
    const review = await buildConfigurationConfirmation({
      kind: "credential_draft",
      before: { credentialType: summary.credentialType, secret: "" },
      after: { credentialType: summary.credentialType, secret: credentialDraft.secret },
    });

    setCredentialSummary(summary);
    setAuditLog((current) => [addAuditEntry("Credential draft", review), ...current].slice(0, 10));
    setCredentialDraft(clearCredentialDraft(credentialDraft));
    setNotice("Credential draft captured and cleared");
  }

  function selectRepository(repository: RepositoryConfig) {
    setSelectedRepositoryId(repository.id);
    setRepositoryDraft(blankRepositoryDraft(repository));
  }

  function selectResource(resource: FeishuResourceConfig) {
    setSelectedResourceId(resource.id ?? null);
    setResourceDraft(blankResourceDraft(resource));
    setSchemaDraft(EMPTY_SCHEMA_DRAFT);
    setMappingRows([createMappingRow()]);
  }

  return (
    <main className="app-shell">
      <div className="page configuration-page">
        <section className="hero hero-configuration">
          <div>
            <p className="kicker">Admin Configuration</p>
            <h1 className="title">Configuration Control</h1>
            <p className="lede">
              Manage project settings, repositories, Feishu resources, prompt versions, model config, credentials, and confirmation flows.
              Every write goes through an explicit review step and gets mirrored into a local audit trail.
            </p>
          </div>
          <div className="hero-meta">
            <span className="status-pill">revision {project.revision}</span>
            <span className="meta-chip">{repositorySummary.count}/5 repositories</span>
            <span className="meta-chip">{mappingSummary.statusLabel}</span>
            <span className="meta-chip">audit {auditLog.length}</span>
          </div>
        </section>

        {notice ? <section className="inline-alert inline-alert-success">{notice}</section> : null}
        {error ? <section className="inline-alert">{error}</section> : null}

        <section className="dashboard-grid">
          <article className="panel dashboard-main">
            <div className="panel-head">
              <div>
                <p className="section-label">Project</p>
                <h2>Project settings</h2>
              </div>
              <span className="mono-chip">project rev {project.revision}</span>
            </div>
            <div className="form-grid form-grid-2">
              <Field label="Name">
                <input className="text-input" value={project.name} onChange={(event) => setProject((current) => ({ ...current, name: event.target.value }))} />
              </Field>
              <Field label="Timezone">
                <input className="text-input" value={project.timezone} onChange={(event) => setProject((current) => ({ ...current, timezone: event.target.value }))} />
              </Field>
              <Field label="Description" span={2}>
                <textarea
                  className="text-area"
                  rows={3}
                  value={project.description ?? ""}
                  onChange={(event) => setProject((current) => ({ ...current, description: event.target.value || null }))}
                />
              </Field>
              <Field label="Default period rule" span={2}>
                <textarea
                  className="text-area mono-text"
                  rows={5}
                  value={defaultPeriodRuleText}
                  onChange={(event) => setDefaultPeriodRuleText(event.target.value)}
                />
              </Field>
              <Field label="Default prompt version">
                <select
                  className="text-input"
                  value={project.default_prompt_version_id ?? ""}
                  onChange={(event) => setProject((current) => ({ ...current, default_prompt_version_id: event.target.value || null }))}
                >
                  <option value="">n/a</option>
                  {activePrompts.map((prompt) => (
                    <option key={prompt.id} value={prompt.id}>
                      v{prompt.version} · {prompt.status}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="panel-actions">
              <button className="primary-button" type="button" onClick={handleProjectSave}>
                Save project
              </button>
            </div>
            <div className="detail-grid">
              <DetailRow label="Created" value={formatDateTime(project.created_at)} />
              <DetailRow label="Updated" value={formatDateTime(project.updated_at)} />
              <DetailRow label="Default prompt" value={project.default_prompt_version_id ?? "n/a"} />
              <DetailRow label="Period rule" value={formatJson(project.default_period_rule)} />
            </div>
          </article>

          <article className="panel dashboard-side">
            <div className="panel-head">
              <div>
                <p className="section-label">Audit</p>
                <h2>Change log</h2>
              </div>
              <span className="mono-chip">{auditLog.length} entries</span>
            </div>
            <div className="stack">
              {auditLog.length > 0 ? (
                auditLog.map((entry) => (
                  <article className="audit-card" key={`${entry.requestHash}-${entry.timestamp}`}>
                    <div className="row-title">
                      <strong>{entry.title}</strong>
                      <span className="mini-pill">{entry.kind}</span>
                    </div>
                    <div className="row-metadata">{entry.revisionLabel}</div>
                    <div className="row-metadata">hash {entry.requestHash.slice(0, 12)}</div>
                    <div className="audit-diff">
                      {entry.review.changeSummary.length > 0 ? (
                        entry.review.changeSummary.map((item) => (
                          <div className="audit-diff-row" key={`${entry.requestHash}-${item.field}`}>
                            <span>{item.field}</span>
                            <strong>
                              {item.before} → {item.after}
                            </strong>
                          </div>
                        ))
                      ) : (
                        <div className="empty-state">No visible diff</div>
                      )}
                    </div>
                  </article>
                ))
              ) : (
                <div className="empty-state">No confirmed writes yet</div>
              )}
            </div>
          </article>
        </section>

        <section className="panel-grid">
          <article className="panel panel-span-7">
            <div className="panel-head">
              <div>
                <p className="section-label">Repositories</p>
                <h2>Repository registry</h2>
              </div>
              <span className={badgeClass(repositorySummary.capacityStatus === "ready" ? "success" : "warning")}>
                {repositorySummary.capacityMessage}
              </span>
            </div>
            <div className="grid grid-4 compact-grid">
              <SummaryCard label="Enabled" value={String(repositorySummary.enabledCount)} />
              <SummaryCard label="Disabled" value={String(repositorySummary.disabledCount)} />
              <SummaryCard label="Healthy" value={String(repositorySummary.connectivityCounts.ok)} />
              <SummaryCard label="Degraded" value={String(repositorySummary.connectivityCounts.degraded + repositorySummary.connectivityCounts.failed)} />
            </div>
            <div className="stack stack-tight">
              {repositorySummary.rows.map((repository) => (
                <article className={`list-row ${selectedRepositoryId === repository.id ? "list-row-active" : ""}`} key={repository.id}>
                  <div className="row-title">
                    <strong>
                      {repository.owner}/{repository.repo}
                    </strong>
                    <span className={badgeClass(repository.connectivityTone)}>{repository.connectivityLabel}</span>
                  </div>
                  <div className="row-metadata">
                    {repository.repositoryType} · branch {repository.defaultBranch} · rev {repository.revision}
                  </div>
                  <div className="row-side">
                    <span>{repository.enabled ? "enabled" : "disabled"}</span>
                    <span>weight {repository.weight}</span>
                  </div>
                  <div className="row-actions">
                    <button className="text-button" type="button" onClick={() => selectRepository(repository)}>
                      Edit
                    </button>
                    <button className="text-button" type="button" onClick={() => handleRepositoryConnectivity(repository)}>
                      Test connectivity
                    </button>
                    <button className="text-button text-button-danger" type="button" disabled={!repository.enabled} onClick={() => handleRepositoryDisable(repository)}>
                      Disable
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </article>

          <article className="panel panel-span-5">
            <div className="panel-head">
              <div>
                <p className="section-label">Repository form</p>
                <h2>{repositoryDraft.id ? "Edit repository" : "Create repository"}</h2>
              </div>
              <span className="mono-chip">max 5</span>
            </div>
            <div className="form-grid">
              <Field label="Owner">
                <input className="text-input" value={repositoryDraft.owner} onChange={(event) => setRepositoryDraft((current) => ({ ...current, owner: event.target.value }))} />
              </Field>
              <Field label="Repo">
                <input className="text-input" value={repositoryDraft.repo} onChange={(event) => setRepositoryDraft((current) => ({ ...current, repo: event.target.value }))} />
              </Field>
              <Field label="Type">
                <input className="text-input" value={repositoryDraft.repository_type} onChange={(event) => setRepositoryDraft((current) => ({ ...current, repository_type: event.target.value }))} />
              </Field>
              <Field label="Weight">
                <input className="text-input" type="number" value={repositoryDraft.weight} onChange={(event) => setRepositoryDraft((current) => ({ ...current, weight: event.target.value }))} />
              </Field>
              <Field label="Default branch">
                <input className="text-input" value={repositoryDraft.default_branch} onChange={(event) => setRepositoryDraft((current) => ({ ...current, default_branch: event.target.value }))} />
              </Field>
              <Field label="Revision">
                <input className="text-input" type="number" value={repositoryDraft.revision} onChange={(event) => setRepositoryDraft((current) => ({ ...current, revision: event.target.value }))} />
              </Field>
              <label className="toggle-row">
                <input type="checkbox" checked={repositoryDraft.enabled} onChange={(event) => setRepositoryDraft((current) => ({ ...current, enabled: event.target.checked }))} />
                <span>Enabled</span>
              </label>
            </div>
            <div className="panel-actions">
              <button className="primary-button" type="button" onClick={handleRepositorySave}>
                Save repository
              </button>
              <button className="secondary-button" type="button" onClick={() => setRepositoryDraft(EMPTY_REPOSITORY_DRAFT)}>
                Reset
              </button>
            </div>
          </article>
        </section>

        <section className="panel-grid">
          <article className="panel panel-span-6">
            <div className="panel-head">
              <div>
                <p className="section-label">Feishu</p>
                <h2>Resource registry</h2>
              </div>
              <span className="mono-chip">{resources.length} items</span>
            </div>
            <div className="stack stack-tight">
              {resources.map((resource) => {
                const tone = resource.last_connectivity_status === "ok" ? "success" : resource.last_connectivity_status === "failed" ? "danger" : "warning";
                return (
                  <article className={`list-row ${selectedResourceId === resource.id ? "list-row-active" : ""}`} key={resource.id}>
                    <div className="row-title">
                      <strong>{resource.name ?? resource.external_id}</strong>
                      <span className={badgeClass(tone)}>{resource.last_connectivity_status ?? "unknown"}</span>
                    </div>
                    <div className="row-metadata">
                      {resource.resource_type} · {resource.external_id}
                    </div>
                    <div className="row-metadata">
                      schema {resource.schema_hash ? `${resource.schema_hash.slice(0, 8)}…${resource.schema_hash.slice(-4)}` : "n/a"} · rev {resource.revision}
                    </div>
                    <div className="row-actions">
                      <button className="text-button" type="button" onClick={() => selectResource(resource)}>
                        Edit
                      </button>
                      <button className="text-button" type="button" onClick={() => handleResourceConnectivity(resource)}>
                        Test connectivity
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </article>

          <article className="panel panel-span-6">
            <div className="panel-head">
              <div>
                <p className="section-label">Feishu form</p>
                <h2>{resourceDraft.id ? "Edit resource" : "Create resource"}</h2>
              </div>
              <span className="mono-chip">{mappingSummary.fingerprintSuffix}</span>
            </div>
            <div className="form-grid form-grid-2">
              <Field label="Type">
                <input className="text-input" value={resourceDraft.resource_type} onChange={(event) => setResourceDraft((current) => ({ ...current, resource_type: event.target.value }))} />
              </Field>
              <Field label="External ID">
                <input className="text-input" value={resourceDraft.external_id} onChange={(event) => setResourceDraft((current) => ({ ...current, external_id: event.target.value }))} />
              </Field>
              <Field label="Name" span={2}>
                <input className="text-input" value={resourceDraft.name} onChange={(event) => setResourceDraft((current) => ({ ...current, name: event.target.value }))} />
              </Field>
              <Field label="Schema hash">
                <input className="text-input mono-text" value={resourceDraft.schema_hash} onChange={(event) => setResourceDraft((current) => ({ ...current, schema_hash: event.target.value }))} />
              </Field>
              <Field label="Revision">
                <input className="text-input" type="number" value={resourceDraft.revision} onChange={(event) => setResourceDraft((current) => ({ ...current, revision: event.target.value }))} />
              </Field>
              <label className="toggle-row">
                <input type="checkbox" checked={resourceDraft.enabled} onChange={(event) => setResourceDraft((current) => ({ ...current, enabled: event.target.checked }))} />
                <span>Enabled</span>
              </label>
            </div>
            <div className="panel-actions">
              <button className="primary-button" type="button" onClick={handleResourceSave}>
                Save resource
              </button>
              <button className="secondary-button" type="button" onClick={() => setResourceDraft(EMPTY_RESOURCE_DRAFT)}>
                Reset
              </button>
            </div>

            <div className="subpanel">
              <div className="panel-head">
                <div>
                  <p className="section-label">Schema preview</p>
                  <h3>Canonical hash</h3>
                </div>
                <span className="mono-chip">{mappingSummary.schemaStatus}</span>
              </div>
              <textarea
                className="text-area mono-text"
                rows={6}
                placeholder='[{"logicalField":"task_id"},{"logicalField":"title"}]'
                value={schemaDraft.jsonText}
                onChange={(event) => setSchemaDraft({ jsonText: event.target.value })}
              />
              <div className="panel-actions">
                <button className="secondary-button" type="button" onClick={handleSchemaCompute}>
                  Compute hash
                </button>
                <button className="primary-button" type="button" onClick={handleSchemaSave}>
                  Save schema snapshot
                </button>
              </div>
            </div>

            <div className="subpanel">
              <div className="panel-head">
                <div>
                  <p className="section-label">Mappings</p>
                  <h3>{mappingSummary.statusLabel}</h3>
                </div>
                <span className={badgeClass(mappingSummary.capabilitySummary.status === "ok" ? "success" : "warning")}>
                  {mappingSummary.capabilitySummary.label}
                </span>
              </div>
              {mappingSummary.missingCriticalFields.length > 0 ? (
                <div className="inline-alert inline-alert-warning">
                  Missing critical fields: {mappingSummary.missingCriticalFields.join(", ")}
                </div>
              ) : null}
              <div className="stack stack-tight">
                {mappingRows.map((row, index) => (
                  <MappingRowEditor
                    key={`${index}-${row.logicalField || "empty"}`}
                    row={row}
                    onChange={(nextRow) => setMappingRows((current) => current.map((item, itemIndex) => (itemIndex === index ? nextRow : item)))}
                    onRemove={() => setMappingRows((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                  />
                ))}
              </div>
              <div className="panel-actions">
                <button className="secondary-button" type="button" onClick={() => setMappingRows((current) => [...current, createMappingRow()])}>
                  Add mapping
                </button>
                <button className="primary-button" type="button" onClick={handleMappingSave}>
                  Save mappings
                </button>
              </div>
            </div>
          </article>
        </section>

        <section className="panel-grid">
          <article className="panel panel-span-6">
            <div className="panel-head">
              <div>
                <p className="section-label">Credentials</p>
                <h2>Secret hygiene</h2>
              </div>
              <span className="mono-chip">{credentialSummary?.fingerprintSuffix || "write-only"}</span>
            </div>
            <p className="lede lede-small">
              This section only stages local secret drafts. There is no backend credential endpoint in the current implementation, so the secret is cleared immediately after staging.
            </p>
            <div className="form-grid form-grid-2">
              <Field label="Credential type">
                <select
                  className="text-input"
                  value={credentialDraft.credentialType ?? "github_pat"}
                  onChange={(event) => setCredentialDraft((current) => ({ ...current, credentialType: event.target.value, status: "draft" }))}
                >
                  <option value="github_pat">github_pat</option>
                  <option value="llm_api_key">llm_api_key</option>
                </select>
              </Field>
              <Field label="Label">
                <input className="text-input" value={credentialDraft.label ?? ""} onChange={(event) => setCredentialDraft((current) => ({ ...current, label: event.target.value }))} />
              </Field>
              <Field label="Secret" span={2}>
                <input className="text-input mono-text" type="password" value={credentialDraft.secret ?? ""} onChange={(event) => setCredentialDraft((current) => ({ ...current, secret: event.target.value }))} />
              </Field>
            </div>
            <div className="panel-actions">
              <button className="primary-button" type="button" onClick={handleCredentialStage}>
                Stage secret
              </button>
            </div>
            {credentialSummary ? (
              <div className="summary-grid">
                <SummaryCard label="Masked" value={credentialSummary.maskedSecret || "n/a"} />
                <SummaryCard label="Fingerprint" value={credentialSummary.fingerprintSuffix || "n/a"} />
              </div>
            ) : null}
          </article>

          <article className="panel panel-span-6">
            <div className="panel-head">
              <div>
                <p className="section-label">Model</p>
                <h2>LLM configuration</h2>
              </div>
              <span className="mono-chip">rev {modelConfig.revision}</span>
            </div>
            <div className="form-grid form-grid-2">
              <Field label="Base URL" span={2}>
                <input className="text-input" value={modelConfig.base_url ?? ""} onChange={(event) => setModelConfig((current) => ({ ...current, base_url: event.target.value || null }))} />
              </Field>
              <Field label="Model">
                <input className="text-input" value={modelConfig.model} onChange={(event) => setModelConfig((current) => ({ ...current, model: event.target.value }))} />
              </Field>
              <Field label="Temperature">
                <input className="text-input" type="number" step="0.1" value={modelConfig.temperature} onChange={(event) => setModelConfig((current) => ({ ...current, temperature: Number(event.target.value) }))} />
              </Field>
              <Field label="Timeout seconds">
                <input className="text-input" type="number" value={modelConfig.timeout_seconds} onChange={(event) => setModelConfig((current) => ({ ...current, timeout_seconds: Number(event.target.value) }))} />
              </Field>
              <Field label="Max retries">
                <input className="text-input" type="number" value={modelConfig.max_retries} onChange={(event) => setModelConfig((current) => ({ ...current, max_retries: Number(event.target.value) }))} />
              </Field>
              <label className="toggle-row">
                <input type="checkbox" checked={modelConfig.stream} onChange={(event) => setModelConfig((current) => ({ ...current, stream: event.target.checked }))} />
                <span>Stream</span>
              </label>
            </div>
            <div className="panel-actions">
              <button className="primary-button" type="button" onClick={handleModelSave}>
                Save model config
              </button>
            </div>
            <div className="detail-grid detail-grid-compact">
              <DetailRow label="Base URL" value={modelConfig.base_url ?? "n/a"} />
              <DetailRow label="Model" value={modelConfig.model} />
              <DetailRow label="Timeout" value={`${modelConfig.timeout_seconds}s`} />
              <DetailRow label="Retries" value={String(modelConfig.max_retries)} />
            </div>
          </article>
        </section>

        <section className="panel-grid">
          <article className="panel panel-span-7">
            <div className="panel-head">
              <div>
                <p className="section-label">Prompts</p>
                <h2>Prompt versions</h2>
              </div>
              <span className="mono-chip">{activePrompts.length} active items</span>
            </div>
            <div className="form-grid form-grid-2">
              <Field label="Prompt type">
                <select className="text-input" value={promptDraft.prompt_type} onChange={(event) => setPromptDraft((current) => ({ ...current, prompt_type: event.target.value }))}>
                  <option value="system">system</option>
                  <option value="report">report</option>
                  <option value="diagnosis">diagnosis</option>
                  <option value="render">render</option>
                </select>
              </Field>
              <Field label="Created by">
                <input className="text-input" value={promptDraft.created_by} onChange={(event) => setPromptDraft((current) => ({ ...current, created_by: event.target.value }))} />
              </Field>
              <Field label="Status">
                <select className="text-input" value={promptDraft.status} onChange={(event) => setPromptDraft((current) => ({ ...current, status: event.target.value }))}>
                  <option value="draft">draft</option>
                  <option value="active">active</option>
                  <option value="retired">retired</option>
                </select>
              </Field>
              <Field label="Content" span={2}>
                <textarea className="text-area" rows={6} value={promptDraft.content} onChange={(event) => setPromptDraft((current) => ({ ...current, content: event.target.value }))} />
              </Field>
            </div>
            <div className="panel-actions">
              <button className="primary-button" type="button" onClick={handlePromptCreate}>
                Create prompt
              </button>
            </div>
            <div className="stack stack-tight">
              {activePrompts.map((prompt) => (
                <article className="list-row" key={prompt.id}>
                  <div className="row-title">
                    <strong>v{prompt.version}</strong>
                    <span className="mini-pill">{prompt.status}</span>
                  </div>
                  <div className="row-metadata">
                    {prompt.prompt_type} · {prompt.created_by} · {prompt.content_hash.slice(0, 10)}
                  </div>
                  <div className="row-actions">
                    <button className="text-button" type="button" onClick={() => handlePromptActivate(prompt)}>
                      Activate
                    </button>
                  </div>
                  <pre className="prompt-preview">{prompt.content}</pre>
                </article>
              ))}
            </div>
          </article>

          <article className="panel panel-span-5">
            <div className="panel-head">
              <div>
                <p className="section-label">Connectivity</p>
                <h2>Verification</h2>
              </div>
              <span className="mono-chip">{connectivityJob?.status ?? "idle"}</span>
            </div>
            <div className="panel-actions">
              <button className="primary-button" type="button" onClick={handleConnectivityRun}>
                Run all connectivity checks
              </button>
            </div>
            {connectivityJob ? (
              <div className="summary-grid">
                <SummaryCard label="Job" value={connectivityJob.id.slice(0, 12)} />
                <SummaryCard label="Status" value={connectivityJob.status} />
              </div>
            ) : null}
            {connectivityJob?.result_summary ? (
              <div className="stack stack-tight">
                {Object.entries(connectivityJob.result_summary).map(([label, value]) => (
                  <article className="connectivity-card" key={label}>
                    <div className="row-title">
                      <strong>{label}</strong>
                      <span className="mini-pill">{(value as { status?: string })?.status ?? "n/a"}</span>
                    </div>
                    <pre>{formatJson(value)}</pre>
                  </article>
                ))}
              </div>
            ) : null}
          </article>
        </section>

        {pendingReview ? (
          <section className="review-overlay" aria-modal="true" role="dialog">
            <article className="review-panel">
              <div className="panel-head">
                <div>
                  <p className="section-label">Confirmation</p>
                  <h2>{pendingReview.title}</h2>
                </div>
                <button className="text-button" type="button" onClick={() => setPendingReview(null)}>
                  Close
                </button>
              </div>
              <div className="review-meta">
                <span className="mono-chip">{pendingReview.review.revisionLabel}</span>
                <span className="mono-chip">hash {pendingReview.review.requestHash.slice(0, 12)}</span>
                {pendingReview.review.requiresFreshRevision ? <span className="mini-pill mini-pill-warning">revision changed</span> : null}
              </div>
              <div className="review-grid">
                <section className="review-box">
                  <h3>Before</h3>
                  <pre>{formatJson(pendingReview.review.before)}</pre>
                </section>
                <section className="review-box">
                  <h3>After</h3>
                  <pre>{formatJson(pendingReview.review.after)}</pre>
                </section>
              </div>
              <div className="review-actions">
                <button className="secondary-button" type="button" onClick={() => setPendingReview(null)} disabled={reviewBusy}>
                  Cancel
                </button>
                <button className="primary-button" type="button" onClick={confirmReview} disabled={reviewBusy}>
                  {reviewBusy ? "Applying..." : pendingReview.confirmLabel}
                </button>
              </div>
            </article>
          </section>
        ) : null}
      </div>
    </main>
  );
}
