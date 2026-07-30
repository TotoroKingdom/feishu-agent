const REPOSITORY_LIMIT = 5;
const SECRET_KEY_PATTERN = /(secret|token|password|api[_-]?key|pat)/i;

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeOptionalText(value) {
  const text = normalizeText(value);
  return text.length > 0 ? text : null;
}

function canonicalize(value) {
  if (Array.isArray(value)) {
    return value.map((item) => canonicalize(item));
  }

  if (value instanceof Date) {
    return value.toISOString();
  }

  if (isPlainObject(value)) {
    return Object.keys(value)
      .sort((left, right) => left.localeCompare(right))
      .reduce((accumulator, key) => {
        accumulator[key] = canonicalize(value[key]);
        return accumulator;
      }, {});
  }

  if (value instanceof Set) {
    return Array.from(value).map((item) => canonicalize(item)).sort((left, right) => {
      return JSON.stringify(left).localeCompare(JSON.stringify(right));
    });
  }

  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean" ||
    value === null
  ) {
    return value;
  }

  if (value === undefined) {
    return null;
  }

  return String(value);
}

function stableJsonStringify(value) {
  return JSON.stringify(canonicalize(value), null, 0);
}

export async function computeCanonicalJsonHash(value) {
  const encoded = new TextEncoder().encode(stableJsonStringify(value));
  const hashBuffer = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(hashBuffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function maskSecret(secret) {
  const text = normalizeText(secret);
  return text.length > 0 ? "•".repeat(text.length) : "";
}

function redactValue(value, keyPath = []) {
  if (Array.isArray(value)) {
    return value.map((item) => redactValue(item, keyPath));
  }

  if (isPlainObject(value)) {
    return Object.keys(value).reduce((accumulator, key) => {
      const nextPath = [...keyPath, key];
      const item = value[key];
      accumulator[key] = SECRET_KEY_PATTERN.test(key) ? "••••" : redactValue(item, nextPath);
      return accumulator;
    }, {});
  }

  if (typeof value === "string" && SECRET_KEY_PATTERN.test(keyPath[keyPath.length - 1] ?? "")) {
    return "••••";
  }

  return value;
}

function stringifyCompact(value) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (typeof value === "string") {
    return value;
  }
  return stableJsonStringify(value);
}

function summarizeConnectivity(status) {
  switch (status) {
    case "ok":
      return { label: "Connected", tone: "success" };
    case "degraded":
      return { label: "Degraded", tone: "warning" };
    case "failed":
      return { label: "Failed", tone: "danger" };
    default:
      return { label: "Unknown", tone: "neutral" };
  }
}

export function summarizeRepositoryConfiguration(repositories) {
  const rows = [...repositories]
    .map((repository) => ({
      id: repository.id,
      externalId: repository.external_id ?? `${repository.owner ?? ""}/${repository.repo ?? ""}`,
      owner: repository.owner ?? "",
      repo: repository.repo ?? "",
      repositoryType: repository.repository_type ?? repository.provider ?? "github",
      weight: Number(repository.weight ?? 0),
      enabled: Boolean(repository.enabled),
      defaultBranch: repository.default_branch ?? "main",
      revision: Number(repository.revision ?? 1),
      status: repository.last_connectivity_status ?? "unknown",
      checkedAt: repository.last_connectivity_at ?? null,
    }))
    .sort((left, right) => {
      if (right.weight !== left.weight) {
        return right.weight - left.weight;
      }
      return left.externalId.localeCompare(right.externalId);
    });

  const connectivityCounts = rows.reduce(
    (counts, row) => {
      const key = row.status === "ok" || row.status === "degraded" || row.status === "failed" ? row.status : "unknown";
      counts[key] += 1;
      return counts;
    },
    { ok: 0, degraded: 0, failed: 0, unknown: 0 },
  );

  const count = rows.length;
  const enabledCount = rows.filter((row) => row.enabled).length;
  const disabledCount = count - enabledCount;

  return {
    count,
    enabledCount,
    disabledCount,
    remainingSlots: Math.max(0, REPOSITORY_LIMIT - count),
    capacityStatus: count > REPOSITORY_LIMIT ? "over_limit" : "ready",
    capacityMessage:
      count > REPOSITORY_LIMIT
        ? `最多 5 个仓库，当前已有 ${count} 个`
        : `${count}/${REPOSITORY_LIMIT} repositories`,
    connectivityCounts,
    rows: rows.map((row) => ({
      ...row,
      connectivityLabel: summarizeConnectivity(row.status).label,
      connectivityTone: summarizeConnectivity(row.status).tone,
    })),
  };
}

export function summarizeFeishuMappingConfiguration(resource, draft) {
  const currentHash = normalizeOptionalText(resource?.schema_hash);
  const submittedHash = normalizeOptionalText(draft?.schemaHash);
  const selectedHash = currentHash ?? submittedHash;
  const schemaStatus =
    currentHash && submittedHash && currentHash !== submittedHash
      ? "conflict"
      : currentHash || submittedHash
        ? "matched"
        : "pending";
  const requiredLogicalFields = [...new Set(draft?.requiredLogicalFields ?? [])].filter(Boolean);
  const fieldRows = (draft?.fields ?? []).map((field) => ({
    logicalField: normalizeText(field.logicalField),
    externalFieldId: normalizeText(field.externalFieldId),
    externalFieldName: normalizeText(field.externalFieldName),
    externalFieldType: normalizeText(field.externalFieldType) || "unknown",
    converter: normalizeText(field.converter) || "passthrough",
    requiredLevel: field.requiredLevel ?? "optional",
    enabled: field.enabled !== false,
  }));
  const mappedFields = new Set(fieldRows.map((field) => field.logicalField));
  const missingCriticalFields = requiredLogicalFields.filter((field) => !mappedFields.has(field));
  const status =
    schemaStatus === "conflict"
      ? "schema_conflict"
      : missingCriticalFields.length > 0
        ? "missing_critical"
        : resource?.enabled === false
          ? "disabled"
          : "ready";

  return {
    resourceId: resource?.id ?? null,
    resourceType: resource?.resource_type ?? "unknown",
    externalId: resource?.external_id ?? "n/a",
    name: resource?.name ?? resource?.external_id ?? "n/a",
    enabled: Boolean(resource?.enabled),
    revision: Number(resource?.revision ?? 1),
    fingerprintSuffix: (selectedHash ?? "n/a").slice(-4),
    schemaStatus,
    schemaMessage:
      schemaStatus === "conflict"
        ? "schema hash 冲突，必须重新加载 schema 再保存映射"
        : schemaStatus === "matched"
          ? "schema hash 已对齐"
          : "schema 未加载",
    status,
    statusLabel:
      status === "ready"
        ? "Ready"
        : status === "missing_critical"
          ? "Missing critical field"
          : status === "schema_conflict"
            ? "Schema conflict"
            : "Disabled",
    missingCriticalFields,
    capabilitySummary: {
      status: resource?.last_connectivity_status ?? "unknown",
      label: summarizeConnectivity(resource?.last_connectivity_status).label,
      checkedAt: resource?.last_connectivity_at ?? null,
    },
    fieldRows,
  };
}

export async function buildCredentialDraftSummary(draft) {
  const secret = normalizeText(draft?.secret);
  const fingerprintHash = secret.length > 0
    ? await computeCanonicalJsonHash({
        credentialType: normalizeText(draft?.credentialType),
        label: normalizeText(draft?.label),
        secret,
      })
    : "";

  return {
    credentialType: normalizeText(draft?.credentialType),
    label: normalizeText(draft?.label),
    status: normalizeText(draft?.status) || "draft",
    maskedSecret: maskSecret(secret),
    secretEcho: "",
    fingerprintSuffix: fingerprintHash.slice(-4),
    hasSecret: secret.length > 0,
  };
}

export function clearCredentialDraft(draft) {
  return {
    ...draft,
    secret: "",
    fingerprintSuffix: "",
  };
}

function summarizeDiff(before, after) {
  const keys = new Set([
    ...Object.keys(isPlainObject(before) ? before : {}),
    ...Object.keys(isPlainObject(after) ? after : {}),
  ]);

  const changes = [];
  for (const key of keys) {
    const previous = before?.[key];
    const next = after?.[key];
    const previousText = stringifyCompact(previous);
    const nextText = stringifyCompact(next);
    if (previousText !== nextText) {
      changes.push({
        field: key,
        before: previousText,
        after: nextText,
      });
    }
  }
  return changes;
}

export async function buildConfigurationConfirmation(change) {
  const before = redactValue(change?.before ?? {});
  const after = redactValue(change?.after ?? {});
  const requestHash = await computeCanonicalJsonHash({
    kind: change?.kind ?? "unknown",
    before,
    after,
  });
  const beforeRevision = Number(change?.before?.revision ?? 0);
  const afterRevision = Number(change?.after?.revision ?? 0);
  const requiresFreshRevision = beforeRevision !== afterRevision;

  return {
    kind: change?.kind ?? "unknown",
    requestHash,
    before,
    after,
    changeSummary: summarizeDiff(before, after),
    canSubmit: true,
    requiresFreshRevision,
    revisionLabel:
      requiresFreshRevision ? `revision ${beforeRevision} → ${afterRevision}` : `revision ${afterRevision}`,
    riskFlags: requiresFreshRevision ? ["revision_changed"] : [],
  };
}
