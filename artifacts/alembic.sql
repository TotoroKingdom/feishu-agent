BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> t8_initial_run_tables

CREATE TABLE projects (
    id VARCHAR(36) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE TABLE project_repositories (
    id VARCHAR(36) NOT NULL, 
    project_id VARCHAR(36) NOT NULL, 
    external_id VARCHAR(300) NOT NULL, 
    provider VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_project_repo UNIQUE (project_id, provider, external_id), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE TABLE feishu_resources (
    id VARCHAR(36) NOT NULL, 
    project_id VARCHAR(36) NOT NULL, 
    resource_type VARCHAR(64) NOT NULL, 
    external_id VARCHAR(300) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_feishu_resource UNIQUE (project_id, resource_type), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE TABLE report_runs (
    id VARCHAR(36) NOT NULL, 
    project_id VARCHAR(36) NOT NULL, 
    period_key VARCHAR(120) NOT NULL, 
    period_start DATE NOT NULL, 
    period_end DATE NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_report_runs_project_period UNIQUE (project_id, period_key), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);

INSERT INTO alembic_version (version_num) VALUES ('t8_initial_run_tables') RETURNING alembic_version.version_num;

-- Running upgrade t8_initial_run_tables -> t9_langgraph_runtime

ALTER TABLE report_runs ADD COLUMN thread_id VARCHAR(128);

ALTER TABLE report_runs ADD COLUMN graph_version VARCHAR(32) DEFAULT 'weekly_report.v1' NOT NULL;

ALTER TABLE report_runs ADD COLUMN state_schema_version INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE report_runs ADD COLUMN current_stage VARCHAR(40) DEFAULT 'created' NOT NULL;

ALTER TABLE report_runs ADD COLUMN current_node VARCHAR(80);

UPDATE report_runs SET thread_id = 'report-run:' || id WHERE thread_id IS NULL;

ALTER TABLE report_runs ALTER COLUMN thread_id SET NOT NULL;

ALTER TABLE report_runs ADD CONSTRAINT uq_report_runs_thread_id UNIQUE (thread_id);

CREATE TABLE run_status_history (
    id SERIAL NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    from_status VARCHAR(40) NOT NULL, 
    to_status VARCHAR(40) NOT NULL, 
    reason_code VARCHAR(64) NOT NULL, 
    actor_type VARCHAR(16) NOT NULL, 
    actor_id VARCHAR(128) NOT NULL, 
    node_name VARCHAR(80), 
    checkpoint_ref VARCHAR(256), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id)
);

CREATE INDEX ix_run_status_history_run_id ON run_status_history (run_id);

UPDATE alembic_version SET version_num='t9_langgraph_runtime' WHERE alembic_version.version_num = 't8_initial_run_tables';

-- Running upgrade t9_langgraph_runtime -> t10_generation_approvals

ALTER TABLE report_runs ADD COLUMN scope_revision INTEGER DEFAULT '1' NOT NULL;

CREATE TABLE human_approvals (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    approval_type VARCHAR(24) NOT NULL, 
    revision INTEGER NOT NULL, 
    status VARCHAR(24) DEFAULT 'pending' NOT NULL, 
    challenge_id VARCHAR(36) NOT NULL, 
    card_message_id VARCHAR(128), 
    requested_from JSON NOT NULL, 
    request_payload_hash VARCHAR(64) NOT NULL, 
    plan_hash VARCHAR(64), 
    actor_id VARCHAR(128), 
    actor_type VARCHAR(16), 
    decision VARCHAR(32), 
    supplement JSON, 
    decided_at TIMESTAMP WITH TIME ZONE, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_human_approvals_revision UNIQUE (run_id, approval_type, revision), 
    CONSTRAINT uq_human_approvals_challenge_id UNIQUE (challenge_id), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_human_approvals_run_id ON human_approvals (run_id);

UPDATE alembic_version SET version_num='t10_generation_approvals' WHERE alembic_version.version_num = 't9_langgraph_runtime';

-- Running upgrade t10_generation_approvals -> t11_source_collection

CREATE TABLE source_data_batches (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    source_type VARCHAR(24) NOT NULL, 
    source_resource_id VARCHAR(36) NOT NULL, 
    entity_type VARCHAR(32) NOT NULL, 
    page_no INTEGER NOT NULL, 
    cursor VARCHAR(512), 
    period_start TIMESTAMP WITH TIME ZONE, 
    period_end TIMESTAMP WITH TIME ZONE, 
    payload JSONB NOT NULL, 
    payload_hash VARCHAR(64) NOT NULL, 
    record_count INTEGER NOT NULL, 
    schema_version VARCHAR(32) NOT NULL, 
    fetch_status VARCHAR(20) NOT NULL, 
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_source_data_batches_identity UNIQUE (run_id, source_type, source_resource_id, entity_type, page_no, payload_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_source_data_batches_run_id ON source_data_batches (run_id);

CREATE INDEX ix_source_data_batches_run_entity ON source_data_batches (run_id, entity_type);

CREATE INDEX ix_source_data_batches_expires_at ON source_data_batches (expires_at);

CREATE TABLE normalized_snapshots (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    source_batch_set_hash VARCHAR(64) NOT NULL, 
    mapping_revision VARCHAR(32) NOT NULL, 
    normalizer_version VARCHAR(32) NOT NULL, 
    entity_count INTEGER NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_normalized_snapshots UNIQUE (run_id, content_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_normalized_snapshots_run_id ON normalized_snapshots (run_id);

CREATE TABLE normalized_entities (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    normalized_snapshot_id VARCHAR(36) NOT NULL, 
    source_type VARCHAR(24) NOT NULL, 
    entity_type VARCHAR(32) NOT NULL, 
    source_resource_id VARCHAR(36) NOT NULL, 
    external_id VARCHAR(128) NOT NULL, 
    repository_id VARCHAR(36), 
    url VARCHAR(512), 
    title VARCHAR(512), 
    state VARCHAR(32), 
    author_external_id VARCHAR(128), 
    assignee_external_ids JSONB NOT NULL, 
    labels JSONB NOT NULL, 
    milestone_external_id VARCHAR(128), 
    created_at_external TIMESTAMP WITH TIME ZONE, 
    updated_at_external TIMESTAMP WITH TIME ZONE, 
    closed_at_external TIMESTAMP WITH TIME ZONE, 
    occurred_at TIMESTAMP WITH TIME ZONE, 
    raw_batch_id VARCHAR(36), 
    raw_summary VARCHAR(512), 
    attributes JSONB NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_normalized_entities_identity UNIQUE (run_id, source_type, source_resource_id, entity_type, external_id, content_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(normalized_snapshot_id) REFERENCES normalized_snapshots (id) ON DELETE CASCADE
);

CREATE INDEX ix_normalized_entities_run_id ON normalized_entities (run_id);

CREATE INDEX ix_normalized_entities_snapshot ON normalized_entities (normalized_snapshot_id);

CREATE TABLE validation_results (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    validation_pass BOOLEAN DEFAULT false NOT NULL, 
    data_quality_status VARCHAR(24) NOT NULL, 
    rule_set_version VARCHAR(32) NOT NULL, 
    critical_count INTEGER NOT NULL, 
    warning_count INTEGER NOT NULL, 
    missing_items JSONB NOT NULL, 
    conflicts JSONB NOT NULL, 
    warnings JSONB NOT NULL, 
    input_snapshot_hash VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_validation_results UNIQUE (run_id, input_snapshot_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_validation_results_run_created ON validation_results (run_id, created_at);

CREATE TABLE tool_executions (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    node_execution_id VARCHAR(128) NOT NULL, 
    tool_name VARCHAR(128) NOT NULL, 
    tool_version VARCHAR(32) NOT NULL, 
    attempt INTEGER NOT NULL, 
    idempotency_key VARCHAR(128) NOT NULL, 
    request_summary JSONB NOT NULL, 
    result_summary JSONB NOT NULL, 
    data_ref VARCHAR(36), 
    provider_request_id VARCHAR(256), 
    status VARCHAR(24) NOT NULL, 
    error_class VARCHAR(128), 
    error_code VARCHAR(64), 
    retryable BOOLEAN DEFAULT false NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    ended_at TIMESTAMP WITH TIME ZONE, 
    duration_ms INTEGER, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_tool_executions_attempt UNIQUE (run_id, idempotency_key, attempt), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_tool_executions_run_id ON tool_executions (run_id);

CREATE INDEX ix_tool_executions_tool_status ON tool_executions (tool_name, status);

UPDATE alembic_version SET version_num='t11_source_collection' WHERE alembic_version.version_num = 't10_generation_approvals';

-- Running upgrade t11_source_collection -> t12_metric_snapshots

CREATE TABLE metric_snapshots (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    normalized_snapshot_id VARCHAR(36) NOT NULL, 
    definition_version VARCHAR(32) NOT NULL, 
    period_start TIMESTAMP WITH TIME ZONE NOT NULL, 
    period_end TIMESTAMP WITH TIME ZONE NOT NULL, 
    metrics JSONB NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_metric_snapshots UNIQUE (run_id, normalized_snapshot_id, definition_version, content_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(normalized_snapshot_id) REFERENCES normalized_snapshots (id) ON DELETE CASCADE
);

CREATE INDEX ix_metric_snapshots_run_id ON metric_snapshots (run_id);

CREATE INDEX ix_metric_snapshots_normalized_snapshot_id ON metric_snapshots (normalized_snapshot_id);

UPDATE alembic_version SET version_num='t12_metric_snapshots' WHERE alembic_version.version_num = 't11_source_collection';

-- Running upgrade t12_metric_snapshots -> t13_report_generation

CREATE TABLE evidence_sets (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    normalized_snapshot_id VARCHAR(36) NOT NULL, 
    metric_snapshot_id VARCHAR(36) NOT NULL, 
    builder_version VARCHAR(32) NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_evidence_sets UNIQUE (run_id, content_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(normalized_snapshot_id) REFERENCES normalized_snapshots (id) ON DELETE CASCADE, 
    FOREIGN KEY(metric_snapshot_id) REFERENCES metric_snapshots (id) ON DELETE CASCADE
);

CREATE INDEX ix_evidence_sets_run_id ON evidence_sets (run_id);

CREATE INDEX ix_evidence_sets_normalized_snapshot_id ON evidence_sets (normalized_snapshot_id);

CREATE INDEX ix_evidence_sets_metric_snapshot_id ON evidence_sets (metric_snapshot_id);

CREATE TABLE evidence_items (
    id VARCHAR(36) NOT NULL, 
    evidence_set_id VARCHAR(36) NOT NULL, 
    evidence_key VARCHAR(128) NOT NULL, 
    source_type VARCHAR(24) NOT NULL, 
    source_resource_id VARCHAR(36) NOT NULL, 
    external_id VARCHAR(128) NOT NULL, 
    url VARCHAR(512), 
    period_start TIMESTAMP WITH TIME ZONE, 
    period_end TIMESTAMP WITH TIME ZONE, 
    evidence_summary VARCHAR(512), 
    confidence FLOAT NOT NULL, 
    normalized_entity_id VARCHAR(36), 
    content_hash VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_evidence_items UNIQUE (evidence_set_id, evidence_key), 
    FOREIGN KEY(evidence_set_id) REFERENCES evidence_sets (id) ON DELETE CASCADE, 
    FOREIGN KEY(normalized_entity_id) REFERENCES normalized_entities (id) ON DELETE CASCADE
);

CREATE INDEX ix_evidence_items_evidence_set_id ON evidence_items (evidence_set_id);

CREATE INDEX ix_evidence_items_normalized_entity_id ON evidence_items (normalized_entity_id);

CREATE TABLE report_versions (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    version INTEGER NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    structured_report JSONB NOT NULL, 
    structured_hash VARCHAR(64) NOT NULL, 
    rendered_content TEXT, 
    content_hash VARCHAR(64) NOT NULL, 
    data_snapshot_hash VARCHAR(64) NOT NULL, 
    prompt_version_ids JSONB NOT NULL, 
    model_info JSONB NOT NULL, 
    confidence FLOAT NOT NULL, 
    data_quality_status VARCHAR(24) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_report_versions_version UNIQUE (run_id, version), 
    CONSTRAINT uq_report_versions_content_hash UNIQUE (run_id, content_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_report_versions_run_id ON report_versions (run_id);

CREATE TABLE report_claims (
    id VARCHAR(36) NOT NULL, 
    report_version_id VARCHAR(36) NOT NULL, 
    claim_key VARCHAR(128) NOT NULL, 
    content VARCHAR(1024) NOT NULL, 
    claim_type VARCHAR(24) NOT NULL, 
    importance VARCHAR(24) NOT NULL, 
    period_start TIMESTAMP WITH TIME ZONE, 
    period_end TIMESTAMP WITH TIME ZONE, 
    confidence FLOAT NOT NULL, 
    grounding_status VARCHAR(24) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_report_claims UNIQUE (report_version_id, claim_key), 
    FOREIGN KEY(report_version_id) REFERENCES report_versions (id) ON DELETE CASCADE
);

CREATE INDEX ix_report_claims_report_version_id ON report_claims (report_version_id);

CREATE TABLE report_evidence (
    id VARCHAR(36) NOT NULL, 
    claim_id VARCHAR(36) NOT NULL, 
    evidence_item_id VARCHAR(36) NOT NULL, 
    citation_order INTEGER NOT NULL, 
    relevance_score FLOAT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_report_evidence UNIQUE (claim_id, evidence_item_id), 
    FOREIGN KEY(claim_id) REFERENCES report_claims (id) ON DELETE CASCADE, 
    FOREIGN KEY(evidence_item_id) REFERENCES evidence_items (id) ON DELETE CASCADE
);

CREATE INDEX ix_report_evidence_claim_id ON report_evidence (claim_id);

CREATE INDEX ix_report_evidence_evidence_item_id ON report_evidence (evidence_item_id);

CREATE INDEX ix_report_evidence_claim_order ON report_evidence (claim_id, citation_order);

UPDATE alembic_version SET version_num='t13_report_generation' WHERE alembic_version.version_num = 't12_metric_snapshots';

-- Running upgrade t13_report_generation -> t15_publish_plans

CREATE TABLE publish_plans (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    report_version_id VARCHAR(36) NOT NULL, 
    version INTEGER NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    canonical_plan JSONB NOT NULL, 
    plan_hash VARCHAR(64) NOT NULL, 
    content_version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    invalidated_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_publish_plans_version UNIQUE (run_id, version), 
    CONSTRAINT uq_publish_plans_plan_hash UNIQUE (run_id, plan_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(report_version_id) REFERENCES report_versions (id) ON DELETE CASCADE
);

CREATE INDEX ix_publish_plans_run_id ON publish_plans (run_id);

CREATE INDEX ix_publish_plans_report_version_id ON publish_plans (report_version_id);

ALTER TABLE report_runs ADD COLUMN approved_publish_plan_id VARCHAR(36);

CREATE INDEX ix_report_runs_approved_publish_plan_id ON report_runs (approved_publish_plan_id);

UPDATE alembic_version SET version_num='t15_publish_plans' WHERE alembic_version.version_num = 't13_report_generation';

-- Running upgrade t15_publish_plans -> t16_side_effect_ledger

CREATE TABLE side_effect_operations (
    id VARCHAR(36) NOT NULL, 
    publish_plan_id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    sequence INTEGER NOT NULL, 
    operation_type VARCHAR(64) NOT NULL, 
    target_ref VARCHAR(512) NOT NULL, 
    target_hash VARCHAR(64) NOT NULL, 
    payload_ref VARCHAR(512) NOT NULL, 
    payload_hash VARCHAR(64) NOT NULL, 
    idempotency_key VARCHAR(128) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    attempt_count INTEGER NOT NULL, 
    external_resource_id VARCHAR(256), 
    external_url VARCHAR(512), 
    provider_request_id VARCHAR(256), 
    verification_status VARCHAR(24), 
    last_error_class VARCHAR(128), 
    last_error_summary VARCHAR(512), 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    version INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_side_effect_operations_sequence UNIQUE (publish_plan_id, sequence), 
    CONSTRAINT uq_side_effect_operations_idempotency_key UNIQUE (idempotency_key), 
    FOREIGN KEY(publish_plan_id) REFERENCES publish_plans (id) ON DELETE CASCADE, 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_side_effect_operations_publish_plan_id ON side_effect_operations (publish_plan_id);

CREATE INDEX ix_side_effect_operations_run_id ON side_effect_operations (run_id);

CREATE INDEX ix_side_effect_operations_run_status ON side_effect_operations (run_id, status);

CREATE TABLE side_effect_attempts (
    id VARCHAR(36) NOT NULL, 
    operation_id VARCHAR(36) NOT NULL, 
    attempt INTEGER NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    request_summary JSONB NOT NULL, 
    provider_request_id VARCHAR(256), 
    response_summary JSONB NOT NULL, 
    error_class VARCHAR(128), 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    ended_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_side_effect_attempts UNIQUE (operation_id, attempt), 
    FOREIGN KEY(operation_id) REFERENCES side_effect_operations (id) ON DELETE CASCADE
);

CREATE INDEX ix_side_effect_attempts_operation_id ON side_effect_attempts (operation_id);

CREATE TABLE report_artifacts (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    report_version_id VARCHAR(36) NOT NULL, 
    artifact_type VARCHAR(32) NOT NULL, 
    operation_id VARCHAR(36) NOT NULL, 
    external_id VARCHAR(256), 
    url VARCHAR(512), 
    target_ref VARCHAR(512) NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_report_artifacts_operation UNIQUE (operation_id), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(report_version_id) REFERENCES report_versions (id) ON DELETE CASCADE, 
    FOREIGN KEY(operation_id) REFERENCES side_effect_operations (id) ON DELETE CASCADE
);

CREATE INDEX ix_report_artifacts_run_id ON report_artifacts (run_id);

CREATE INDEX ix_report_artifacts_report_version_id ON report_artifacts (report_version_id);

CREATE INDEX ix_report_artifacts_operation_id ON report_artifacts (operation_id);

CREATE INDEX ix_report_artifacts_run_type ON report_artifacts (run_id, artifact_type);

UPDATE alembic_version SET version_num='t16_side_effect_ledger' WHERE alembic_version.version_num = 't15_publish_plans';

-- Running upgrade t16_side_effect_ledger -> t19_callback_inbox_outbox

CREATE TABLE callback_events (
    id SERIAL NOT NULL, 
    provider VARCHAR(32) NOT NULL, 
    external_event_id VARCHAR(256) NOT NULL, 
    event_type VARCHAR(64) NOT NULL, 
    payload_hash VARCHAR(64) NOT NULL, 
    actor_id VARCHAR(128) NOT NULL, 
    run_id VARCHAR(36), 
    status VARCHAR(24) NOT NULL, 
    attempt_count INTEGER NOT NULL, 
    received_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    claimed_at TIMESTAMP WITH TIME ZONE, 
    claimed_by VARCHAR(128), 
    lease_expires_at TIMESTAMP WITH TIME ZONE, 
    next_attempt_at TIMESTAMP WITH TIME ZONE, 
    processed_at TIMESTAMP WITH TIME ZONE, 
    dead_lettered_at TIMESTAMP WITH TIME ZONE, 
    last_error_class VARCHAR(128), 
    last_error_summary VARCHAR(512), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_callback_events_provider_event_id UNIQUE (provider, external_event_id), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_callback_events_run_id ON callback_events (run_id);

CREATE INDEX ix_callback_events_status_received_at ON callback_events (status, received_at);

CREATE TABLE outbox_messages (
    id VARCHAR(36) NOT NULL, 
    topic VARCHAR(128) NOT NULL, 
    aggregate_type VARCHAR(64) NOT NULL, 
    aggregate_id VARCHAR(128) NOT NULL, 
    payload JSONB NOT NULL, 
    dedupe_key VARCHAR(64) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    attempt_count INTEGER NOT NULL, 
    available_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    claimed_at TIMESTAMP WITH TIME ZONE, 
    claimed_by VARCHAR(128), 
    lease_expires_at TIMESTAMP WITH TIME ZONE, 
    provider_request_id VARCHAR(256), 
    external_message_id VARCHAR(256), 
    published_at TIMESTAMP WITH TIME ZONE, 
    dead_lettered_at TIMESTAMP WITH TIME ZONE, 
    last_error_class VARCHAR(128), 
    last_error_summary VARCHAR(512), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_outbox_messages_dedupe_key UNIQUE (dedupe_key)
);

CREATE INDEX ix_outbox_messages_status_available_at ON outbox_messages (status, available_at);

CREATE INDEX ix_outbox_messages_topic ON outbox_messages (topic);

UPDATE alembic_version SET version_num='t19_callback_inbox_outbox' WHERE alembic_version.version_num = 't16_side_effect_ledger';

-- Running upgrade t19_callback_inbox_outbox -> t20_feishu_identity_cards_resume

CREATE TABLE feishu_message_deliveries (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36), 
    onboarding_session_id VARCHAR(36), 
    purpose VARCHAR(64) NOT NULL, 
    revision INTEGER NOT NULL, 
    recipient_type VARCHAR(16) NOT NULL, 
    recipient_id VARCHAR(128) NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    idempotency_key VARCHAR(128) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    external_message_id VARCHAR(256), 
    attempt_count INTEGER NOT NULL, 
    last_error_summary VARCHAR(512), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_feishu_message_deliveries_idempotency_key UNIQUE (idempotency_key), 
    CONSTRAINT uq_feishu_message_deliveries_run_purpose_revision_recipient UNIQUE (run_id, purpose, revision, recipient_type, recipient_id), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_feishu_message_deliveries_status_created_at ON feishu_message_deliveries (status, created_at);

CREATE INDEX ix_feishu_message_deliveries_run_id ON feishu_message_deliveries (run_id);

UPDATE alembic_version SET version_num='t20_feishu_identity_cards_resume' WHERE alembic_version.version_num = 't19_callback_inbox_outbox';

-- Running upgrade t20_feishu_identity_cards_resume -> t22_github_credentials

CREATE TABLE encrypted_credentials (
    id VARCHAR(36) NOT NULL, 
    project_id VARCHAR(36), 
    credential_type VARCHAR(32) NOT NULL, 
    label VARCHAR(128) NOT NULL, 
    ciphertext BYTEA NOT NULL, 
    nonce BYTEA NOT NULL, 
    key_version VARCHAR(32) NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    last_validated_at TIMESTAMP WITH TIME ZONE, 
    created_by VARCHAR(128) NOT NULL, 
    updated_by VARCHAR(128) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_encrypted_credentials_label UNIQUE (project_id, credential_type, label), 
    CONSTRAINT uq_encrypted_credentials_fingerprint UNIQUE (fingerprint), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_encrypted_credentials_project_type_status ON encrypted_credentials (project_id, credential_type, status);

UPDATE alembic_version SET version_num='t22_github_credentials' WHERE alembic_version.version_num = 't20_feishu_identity_cards_resume';

-- Running upgrade t22_github_credentials -> t30_diagnosis_records

CREATE TABLE diagnosis_records (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    validation_result_id VARCHAR(36), 
    problem_key VARCHAR(128) NOT NULL, 
    problem_type VARCHAR(64) NOT NULL, 
    severity VARCHAR(24) NOT NULL, 
    observation JSON NOT NULL, 
    diagnosis JSON NOT NULL, 
    impact_scope JSON NOT NULL, 
    recoverability VARCHAR(24) NOT NULL, 
    planned_action VARCHAR(64) NOT NULL, 
    action_params JSON NOT NULL, 
    attempt INTEGER NOT NULL, 
    result VARCHAR(24) NOT NULL, 
    next_node VARCHAR(80), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    resolved_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_diagnosis_records_attempt UNIQUE (run_id, problem_key, attempt), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(validation_result_id) REFERENCES validation_results (id) ON DELETE SET NULL
);

CREATE INDEX ix_diagnosis_records_run_created_at ON diagnosis_records (run_id, created_at);

CREATE INDEX ix_diagnosis_records_run_id ON diagnosis_records (run_id);

CREATE INDEX ix_diagnosis_records_validation_result_id ON diagnosis_records (validation_result_id);

UPDATE alembic_version SET version_num='t30_diagnosis_records' WHERE alembic_version.version_num = 't22_github_credentials';

-- Running upgrade t30_diagnosis_records -> t35_configuration

CREATE TABLE prompt_versions (
    id VARCHAR(36) NOT NULL, 
    prompt_type VARCHAR(32) NOT NULL, 
    version INTEGER NOT NULL, 
    content TEXT NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    model_constraints JSON NOT NULL, 
    created_by VARCHAR(128) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_prompt_versions_type_version UNIQUE (prompt_type, version)
);

CREATE INDEX ix_prompt_versions_type_status ON prompt_versions (prompt_type, status);

CREATE TABLE model_configs (
    id VARCHAR(36) NOT NULL, 
    scope VARCHAR(32) NOT NULL, 
    base_url VARCHAR(512), 
    model VARCHAR(128) NOT NULL, 
    temperature FLOAT NOT NULL, 
    timeout_seconds INTEGER NOT NULL, 
    max_retries INTEGER NOT NULL, 
    stream BOOLEAN NOT NULL, 
    revision INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_model_configs_scope UNIQUE (scope)
);

CREATE TABLE feishu_field_mappings (
    id VARCHAR(36) NOT NULL, 
    resource_id VARCHAR(36) NOT NULL, 
    logical_field VARCHAR(128) NOT NULL, 
    external_field_id VARCHAR(128) NOT NULL, 
    external_field_name VARCHAR(256), 
    external_field_type VARCHAR(64), 
    converter VARCHAR(64), 
    required_level VARCHAR(16) NOT NULL, 
    mapping_options JSON NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_feishu_field_mappings_logical UNIQUE (resource_id, logical_field), 
    CONSTRAINT uq_feishu_field_mappings_external UNIQUE (resource_id, external_field_id), 
    FOREIGN KEY(resource_id) REFERENCES feishu_resources (id) ON DELETE CASCADE
);

CREATE INDEX ix_feishu_field_mappings_resource_id ON feishu_field_mappings (resource_id);

CREATE TABLE async_jobs (
    id VARCHAR(36) NOT NULL, 
    job_type VARCHAR(64) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    run_id VARCHAR(36), 
    requested_by VARCHAR(128) NOT NULL, 
    request_hash VARCHAR(64) NOT NULL, 
    result_summary JSON NOT NULL, 
    error_code VARCHAR(64), 
    error_summary VARCHAR(512), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_async_jobs_request UNIQUE (job_type, requested_by, request_hash), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE SET NULL
);

CREATE INDEX ix_async_jobs_status_created ON async_jobs (status, created_at);

ALTER TABLE projects ADD COLUMN description VARCHAR(512);

ALTER TABLE projects ADD COLUMN default_period_rule JSON DEFAULT '{}' NOT NULL;

ALTER TABLE projects ADD COLUMN default_prompt_version_id VARCHAR(36);

ALTER TABLE projects ADD COLUMN revision INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE projects ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;

ALTER TABLE project_repositories ADD COLUMN owner VARCHAR(128);

ALTER TABLE project_repositories ADD COLUMN repo VARCHAR(128);

ALTER TABLE project_repositories ADD COLUMN repository_type VARCHAR(32);

ALTER TABLE project_repositories ADD COLUMN weight INTEGER DEFAULT '100' NOT NULL;

ALTER TABLE project_repositories ADD COLUMN enabled BOOLEAN DEFAULT true NOT NULL;

ALTER TABLE project_repositories ADD COLUMN default_branch VARCHAR(128);

ALTER TABLE project_repositories ADD COLUMN last_connectivity_status VARCHAR(24);

ALTER TABLE project_repositories ADD COLUMN last_connectivity_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE project_repositories ADD COLUMN revision INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE project_repositories ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;

ALTER TABLE feishu_resources ADD COLUMN name VARCHAR(256);

ALTER TABLE feishu_resources ADD COLUMN schema_hash VARCHAR(64);

ALTER TABLE feishu_resources ADD COLUMN enabled BOOLEAN DEFAULT true NOT NULL;

ALTER TABLE feishu_resources ADD COLUMN revision INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE feishu_resources ADD COLUMN last_connectivity_status VARCHAR(24);

ALTER TABLE feishu_resources ADD COLUMN last_connectivity_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE feishu_resources ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;

UPDATE alembic_version SET version_num='t35_configuration' WHERE alembic_version.version_num = 't30_diagnosis_records';

-- Running upgrade t35_configuration -> t37_admin_auth

CREATE TABLE admin_users (
    id VARCHAR(36) NOT NULL, 
    username VARCHAR(64) NOT NULL, 
    password_hash VARCHAR(256) NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    failed_login_count INTEGER NOT NULL, 
    locked_until TIMESTAMP WITH TIME ZONE, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_admin_users_username UNIQUE (username)
);

CREATE TABLE admin_sessions (
    id VARCHAR(36) NOT NULL, 
    admin_user_id VARCHAR(36) NOT NULL, 
    refresh_token_hash VARCHAR(64) NOT NULL, 
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    ip_hash VARCHAR(64), 
    user_agent_summary VARCHAR(512), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_admin_sessions_refresh_token_hash UNIQUE (refresh_token_hash), 
    FOREIGN KEY(admin_user_id) REFERENCES admin_users (id) ON DELETE CASCADE
);

CREATE INDEX ix_admin_sessions_admin_user_id ON admin_sessions (admin_user_id);

CREATE TABLE login_audits (
    id VARCHAR(36) NOT NULL, 
    admin_user_id VARCHAR(36), 
    username VARCHAR(64) NOT NULL, 
    success BOOLEAN NOT NULL, 
    failure_reason VARCHAR(128), 
    ip_hash VARCHAR(64), 
    user_agent_summary VARCHAR(512), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(admin_user_id) REFERENCES admin_users (id) ON DELETE SET NULL
);

CREATE INDEX ix_login_audits_username_created_at ON login_audits (username, created_at);

UPDATE alembic_version SET version_num='t37_admin_auth' WHERE alembic_version.version_num = 't35_configuration';

-- Running upgrade t37_admin_auth -> t38_schedules

CREATE TABLE schedule_configs (
    id VARCHAR(36) NOT NULL, 
    project_id VARCHAR(36) NOT NULL, 
    cron_expression VARCHAR(128) NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    enabled BOOLEAN DEFAULT false NOT NULL, 
    misfire_policy VARCHAR(24) DEFAULT 'fire_once' NOT NULL, 
    next_fire_at TIMESTAMP WITH TIME ZONE, 
    last_fire_at TIMESTAMP WITH TIME ZONE, 
    revision INTEGER DEFAULT '1' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_schedule_configs_project_id UNIQUE (project_id), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE INDEX ix_schedule_configs_project_id ON schedule_configs (project_id);

CREATE INDEX ix_schedule_configs_enabled_next_fire_at ON schedule_configs (enabled, next_fire_at);

UPDATE alembic_version SET version_num='t38_schedules' WHERE alembic_version.version_num = 't37_admin_auth';

-- Running upgrade t38_schedules -> t39_observability

CREATE TABLE node_executions (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    node_name VARCHAR(80) NOT NULL, 
    node_attempt INTEGER NOT NULL, 
    checkpoint_before VARCHAR(256), 
    checkpoint_after VARCHAR(256), 
    status VARCHAR(20) NOT NULL, 
    input_summary JSON NOT NULL, 
    output_summary JSON NOT NULL, 
    error_class VARCHAR(128), 
    error_summary VARCHAR(512), 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    ended_at TIMESTAMP WITH TIME ZONE, 
    duration_ms INTEGER, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_node_executions_attempt UNIQUE (run_id, node_name, node_attempt), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_node_executions_run_id ON node_executions (run_id);

CREATE INDEX ix_node_executions_run_started ON node_executions (run_id, started_at);

CREATE TABLE llm_executions (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    node_execution_id VARCHAR(36) NOT NULL, 
    provider VARCHAR(64) NOT NULL, 
    model VARCHAR(128) NOT NULL, 
    prompt_type VARCHAR(64) NOT NULL, 
    prompt_version_id VARCHAR(36), 
    input_hash VARCHAR(64) NOT NULL, 
    output_ref VARCHAR(256), 
    status VARCHAR(24) NOT NULL, 
    schema_valid BOOLEAN DEFAULT false NOT NULL, 
    input_tokens INTEGER, 
    output_tokens INTEGER, 
    total_tokens INTEGER, 
    duration_ms INTEGER, 
    error_class VARCHAR(128), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(node_execution_id) REFERENCES node_executions (id) ON DELETE CASCADE
);

CREATE INDEX ix_llm_executions_run_id ON llm_executions (run_id);

CREATE INDEX ix_llm_executions_node_execution_id ON llm_executions (node_execution_id);

CREATE INDEX ix_llm_executions_run_created_at ON llm_executions (run_id, created_at);

CREATE INDEX ix_llm_executions_node_created_at ON llm_executions (node_execution_id, created_at);

CREATE TABLE audit_logs (
    id SERIAL NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    request_id VARCHAR(128), 
    run_id VARCHAR(36), 
    actor_type VARCHAR(16) NOT NULL, 
    actor_id VARCHAR(128) NOT NULL, 
    action VARCHAR(64) NOT NULL, 
    resource_type VARCHAR(64) NOT NULL, 
    resource_id VARCHAR(128) NOT NULL, 
    before_summary JSON NOT NULL, 
    after_summary JSON NOT NULL, 
    result VARCHAR(24) NOT NULL, 
    ip_hash VARCHAR(128), 
    metadata JSON NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES report_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_audit_logs_run_id ON audit_logs (run_id);

CREATE INDEX ix_audit_logs_run_occurred ON audit_logs (run_id, occurred_at);

CREATE INDEX ix_audit_logs_actor_occurred ON audit_logs (actor_id, occurred_at);

CREATE INDEX ix_audit_logs_action_occurred ON audit_logs (action, occurred_at);

CREATE INDEX ix_tool_executions_run_started ON tool_executions (run_id, started_at);

CREATE INDEX ix_tool_executions_tool_status_started ON tool_executions (tool_name, status, started_at);

CREATE INDEX ix_tool_executions_node_execution_id ON tool_executions (node_execution_id);

UPDATE alembic_version SET version_num='t39_observability' WHERE alembic_version.version_num = 't38_schedules';

-- Running upgrade t39_observability -> t41_onboarding

CREATE TABLE onboarding_sessions (
    id VARCHAR(36) NOT NULL, 
    feishu_actor_id VARCHAR(128) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    current_step VARCHAR(64) NOT NULL, 
    draft_config JSON NOT NULL, 
    credential_ref VARCHAR(36), 
    card_message_id VARCHAR(128), 
    revision INTEGER NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(credential_ref) REFERENCES encrypted_credentials (id)
);

CREATE INDEX ix_onboarding_sessions_actor_status ON onboarding_sessions (feishu_actor_id, status);

CREATE UNIQUE INDEX uq_onboarding_sessions_active_actor ON onboarding_sessions (feishu_actor_id) WHERE status IN ('in_progress', 'pending_confirmation');

CREATE INDEX ix_onboarding_sessions_credential_ref ON onboarding_sessions (credential_ref);

UPDATE alembic_version SET version_num='t41_onboarding' WHERE alembic_version.version_num = 't39_observability';

-- Running upgrade t41_onboarding -> t42_run_leases_lifecycle

ALTER TABLE report_runs ADD COLUMN lease_owner VARCHAR(128);

ALTER TABLE report_runs ADD COLUMN lease_expires_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE report_runs ADD COLUMN heartbeat_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE report_runs ADD COLUMN version INTEGER DEFAULT 1 NOT NULL;

CREATE INDEX ix_report_runs_status_lease_expires_at ON report_runs (status, lease_expires_at);

ALTER TABLE side_effect_operations ADD COLUMN lease_owner VARCHAR(128);

ALTER TABLE side_effect_operations ADD COLUMN lease_expires_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE side_effect_operations ADD COLUMN heartbeat_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX ix_side_effect_operations_status_lease_expires_at ON side_effect_operations (status, lease_expires_at);

UPDATE alembic_version SET version_num='t42_run_leases_lifecycle' WHERE alembic_version.version_num = 't41_onboarding';

COMMIT;

