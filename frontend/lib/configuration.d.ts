export type RepositoryStatus = string;

export type RepositoryConfig = {
  id: string;
  owner?: string | null;
  repo?: string | null;
  repository_type?: string | null;
  external_id?: string | null;
  provider?: string | null;
  weight?: number | null;
  enabled?: boolean | null;
  default_branch?: string | null;
  last_connectivity_status?: RepositoryStatus | null;
  last_connectivity_at?: string | null;
  revision?: number | null;
  updated_at?: string | null;
};

export type RepositorySummaryRow = {
  id: string;
  externalId: string;
  owner: string;
  repo: string;
  repositoryType: string;
  weight: number;
  enabled: boolean;
  defaultBranch: string;
  revision: number;
  status: RepositoryStatus;
  checkedAt: string | null;
  connectivityLabel: string;
  connectivityTone: "success" | "warning" | "danger" | "neutral";
};

export type RepositoryConfigurationSummary = {
  count: number;
  enabledCount: number;
  disabledCount: number;
  remainingSlots: number;
  capacityStatus: "ready" | "over_limit";
  capacityMessage: string;
  connectivityCounts: Record<"ok" | "degraded" | "failed" | "unknown", number>;
  rows: RepositorySummaryRow[];
};

export type FeishuFieldDraft = {
  logicalField: string;
  externalFieldId: string;
  externalFieldName?: string | null;
  externalFieldType?: string | null;
  converter?: string | null;
  requiredLevel?: "critical" | "required" | "optional" | string;
  mappingOptions?: Record<string, unknown>;
  enabled?: boolean;
};

export type FeishuMappingDraft = {
  schemaHash?: string | null;
  requiredLogicalFields?: string[];
  fields?: FeishuFieldDraft[];
};

export type FeishuResourceConfig = {
  id?: string | null;
  resource_type?: string | null;
  external_id?: string | null;
  name?: string | null;
  schema_hash?: string | null;
  enabled?: boolean | null;
  revision?: number | null;
  last_connectivity_status?: RepositoryStatus | null;
  last_connectivity_at?: string | null;
  updated_at?: string | null;
};

export type FeishuMappingSummary = {
  resourceId: string | null;
  resourceType: string;
  externalId: string;
  name: string;
  enabled: boolean;
  revision: number;
  fingerprintSuffix: string;
  schemaStatus: "matched" | "conflict" | "pending";
  schemaMessage: string;
  status: "ready" | "missing_critical" | "schema_conflict" | "disabled";
  statusLabel: string;
  missingCriticalFields: string[];
  capabilitySummary: {
    status: RepositoryStatus;
    label: string;
    checkedAt: string | null;
  };
  fieldRows: Array<{
    logicalField: string;
    externalFieldId: string;
    externalFieldName: string;
    externalFieldType: string;
    converter: string;
    requiredLevel: string;
    enabled: boolean;
  }>;
};

export type CredentialDraft = {
  credentialType?: string | null;
  label?: string | null;
  status?: string | null;
  secret?: string | null;
  fingerprintSuffix?: string | null;
};

export type CredentialDraftSummary = {
  credentialType: string;
  label: string;
  status: string;
  maskedSecret: string;
  secretEcho: string;
  fingerprintSuffix: string;
  hasSecret: boolean;
};

export type ConfigurationChange = {
  kind?: string | null;
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
};

export type ConfigurationConfirmation = {
  kind: string;
  requestHash: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  changeSummary: Array<{ field: string; before: string; after: string }>;
  canSubmit: boolean;
  requiresFreshRevision: boolean;
  revisionLabel: string;
  riskFlags: string[];
};

export declare function computeCanonicalJsonHash(value: unknown): Promise<string>;
export declare function maskSecret(secret: string | null | undefined): string;
export declare function summarizeRepositoryConfiguration(
  repositories: RepositoryConfig[],
): RepositoryConfigurationSummary;
export declare function summarizeFeishuMappingConfiguration(
  resource: FeishuResourceConfig | null | undefined,
  draft: FeishuMappingDraft | null | undefined,
): FeishuMappingSummary;
export declare function buildCredentialDraftSummary(
  draft: CredentialDraft | null | undefined,
): Promise<CredentialDraftSummary>;
export declare function clearCredentialDraft<T extends CredentialDraft>(draft: T): T & {
  secret: "";
  fingerprintSuffix: "";
};
export declare function buildConfigurationConfirmation(
  change: ConfigurationChange,
): Promise<ConfigurationConfirmation>;
