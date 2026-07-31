--
-- PostgreSQL database dump
--

-- Dumped from database version 16.6
-- Dumped by pg_dump version 16.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.validation_results DROP CONSTRAINT IF EXISTS validation_results_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.tool_executions DROP CONSTRAINT IF EXISTS tool_executions_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.source_data_batches DROP CONSTRAINT IF EXISTS source_data_batches_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.side_effect_operations DROP CONSTRAINT IF EXISTS side_effect_operations_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.side_effect_operations DROP CONSTRAINT IF EXISTS side_effect_operations_publish_plan_id_fkey;
ALTER TABLE IF EXISTS ONLY public.side_effect_attempts DROP CONSTRAINT IF EXISTS side_effect_attempts_operation_id_fkey;
ALTER TABLE IF EXISTS ONLY public.run_status_history DROP CONSTRAINT IF EXISTS run_status_history_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.report_versions DROP CONSTRAINT IF EXISTS report_versions_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.report_runs DROP CONSTRAINT IF EXISTS report_runs_project_id_fkey;
ALTER TABLE IF EXISTS ONLY public.report_evidence DROP CONSTRAINT IF EXISTS report_evidence_evidence_item_id_fkey;
ALTER TABLE IF EXISTS ONLY public.report_evidence DROP CONSTRAINT IF EXISTS report_evidence_claim_id_fkey;
ALTER TABLE IF EXISTS ONLY public.report_claims DROP CONSTRAINT IF EXISTS report_claims_report_version_id_fkey;
ALTER TABLE IF EXISTS ONLY public.report_artifacts DROP CONSTRAINT IF EXISTS report_artifacts_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.report_artifacts DROP CONSTRAINT IF EXISTS report_artifacts_report_version_id_fkey;
ALTER TABLE IF EXISTS ONLY public.report_artifacts DROP CONSTRAINT IF EXISTS report_artifacts_operation_id_fkey;
ALTER TABLE IF EXISTS ONLY public.publish_plans DROP CONSTRAINT IF EXISTS publish_plans_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.publish_plans DROP CONSTRAINT IF EXISTS publish_plans_report_version_id_fkey;
ALTER TABLE IF EXISTS ONLY public.project_repositories DROP CONSTRAINT IF EXISTS project_repositories_project_id_fkey;
ALTER TABLE IF EXISTS ONLY public.onboarding_sessions DROP CONSTRAINT IF EXISTS onboarding_sessions_credential_ref_fkey;
ALTER TABLE IF EXISTS ONLY public.normalized_snapshots DROP CONSTRAINT IF EXISTS normalized_snapshots_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.normalized_entities DROP CONSTRAINT IF EXISTS normalized_entities_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.normalized_entities DROP CONSTRAINT IF EXISTS normalized_entities_normalized_snapshot_id_fkey;
ALTER TABLE IF EXISTS ONLY public.node_executions DROP CONSTRAINT IF EXISTS node_executions_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.metric_snapshots DROP CONSTRAINT IF EXISTS metric_snapshots_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.metric_snapshots DROP CONSTRAINT IF EXISTS metric_snapshots_normalized_snapshot_id_fkey;
ALTER TABLE IF EXISTS ONLY public.llm_executions DROP CONSTRAINT IF EXISTS llm_executions_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.llm_executions DROP CONSTRAINT IF EXISTS llm_executions_node_execution_id_fkey;
ALTER TABLE IF EXISTS ONLY public.human_approvals DROP CONSTRAINT IF EXISTS human_approvals_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.feishu_resources DROP CONSTRAINT IF EXISTS feishu_resources_project_id_fkey;
ALTER TABLE IF EXISTS ONLY public.feishu_message_deliveries DROP CONSTRAINT IF EXISTS feishu_message_deliveries_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.feishu_field_mappings DROP CONSTRAINT IF EXISTS feishu_field_mappings_resource_id_fkey;
ALTER TABLE IF EXISTS ONLY public.evidence_sets DROP CONSTRAINT IF EXISTS evidence_sets_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.evidence_sets DROP CONSTRAINT IF EXISTS evidence_sets_normalized_snapshot_id_fkey;
ALTER TABLE IF EXISTS ONLY public.evidence_sets DROP CONSTRAINT IF EXISTS evidence_sets_metric_snapshot_id_fkey;
ALTER TABLE IF EXISTS ONLY public.evidence_items DROP CONSTRAINT IF EXISTS evidence_items_normalized_entity_id_fkey;
ALTER TABLE IF EXISTS ONLY public.evidence_items DROP CONSTRAINT IF EXISTS evidence_items_evidence_set_id_fkey;
ALTER TABLE IF EXISTS ONLY public.encrypted_credentials DROP CONSTRAINT IF EXISTS encrypted_credentials_project_id_fkey;
ALTER TABLE IF EXISTS ONLY public.diagnosis_records DROP CONSTRAINT IF EXISTS diagnosis_records_validation_result_id_fkey;
ALTER TABLE IF EXISTS ONLY public.diagnosis_records DROP CONSTRAINT IF EXISTS diagnosis_records_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.callback_events DROP CONSTRAINT IF EXISTS callback_events_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.audit_logs DROP CONSTRAINT IF EXISTS audit_logs_run_id_fkey;
ALTER TABLE IF EXISTS ONLY public.async_jobs DROP CONSTRAINT IF EXISTS async_jobs_run_id_fkey;
DROP INDEX IF EXISTS public.uq_onboarding_sessions_active_actor;
DROP INDEX IF EXISTS public.ix_validation_results_run_created;
DROP INDEX IF EXISTS public.ix_tool_executions_tool_status_started;
DROP INDEX IF EXISTS public.ix_tool_executions_tool_status;
DROP INDEX IF EXISTS public.ix_tool_executions_run_started;
DROP INDEX IF EXISTS public.ix_tool_executions_run_id;
DROP INDEX IF EXISTS public.ix_tool_executions_node_execution_id;
DROP INDEX IF EXISTS public.ix_source_data_batches_run_id;
DROP INDEX IF EXISTS public.ix_source_data_batches_run_entity;
DROP INDEX IF EXISTS public.ix_source_data_batches_expires_at;
DROP INDEX IF EXISTS public.ix_side_effect_operations_status_lease_expires_at;
DROP INDEX IF EXISTS public.ix_side_effect_operations_run_status;
DROP INDEX IF EXISTS public.ix_side_effect_operations_run_id;
DROP INDEX IF EXISTS public.ix_side_effect_operations_publish_plan_id;
DROP INDEX IF EXISTS public.ix_side_effect_attempts_operation_id;
DROP INDEX IF EXISTS public.ix_run_status_history_run_id;
DROP INDEX IF EXISTS public.ix_report_versions_run_id;
DROP INDEX IF EXISTS public.ix_report_runs_status_lease_expires_at;
DROP INDEX IF EXISTS public.ix_report_runs_approved_publish_plan_id;
DROP INDEX IF EXISTS public.ix_report_evidence_evidence_item_id;
DROP INDEX IF EXISTS public.ix_report_evidence_claim_order;
DROP INDEX IF EXISTS public.ix_report_evidence_claim_id;
DROP INDEX IF EXISTS public.ix_report_claims_report_version_id;
DROP INDEX IF EXISTS public.ix_report_artifacts_run_type;
DROP INDEX IF EXISTS public.ix_report_artifacts_run_id;
DROP INDEX IF EXISTS public.ix_report_artifacts_report_version_id;
DROP INDEX IF EXISTS public.ix_report_artifacts_operation_id;
DROP INDEX IF EXISTS public.ix_publish_plans_run_id;
DROP INDEX IF EXISTS public.ix_publish_plans_report_version_id;
DROP INDEX IF EXISTS public.ix_prompt_versions_type_status;
DROP INDEX IF EXISTS public.ix_outbox_messages_topic;
DROP INDEX IF EXISTS public.ix_outbox_messages_status_available_at;
DROP INDEX IF EXISTS public.ix_onboarding_sessions_credential_ref;
DROP INDEX IF EXISTS public.ix_onboarding_sessions_actor_status;
DROP INDEX IF EXISTS public.ix_normalized_snapshots_run_id;
DROP INDEX IF EXISTS public.ix_normalized_entities_snapshot;
DROP INDEX IF EXISTS public.ix_normalized_entities_run_id;
DROP INDEX IF EXISTS public.ix_node_executions_run_started;
DROP INDEX IF EXISTS public.ix_node_executions_run_id;
DROP INDEX IF EXISTS public.ix_metric_snapshots_run_id;
DROP INDEX IF EXISTS public.ix_metric_snapshots_normalized_snapshot_id;
DROP INDEX IF EXISTS public.ix_llm_executions_run_id;
DROP INDEX IF EXISTS public.ix_llm_executions_run_created_at;
DROP INDEX IF EXISTS public.ix_llm_executions_node_execution_id;
DROP INDEX IF EXISTS public.ix_llm_executions_node_created_at;
DROP INDEX IF EXISTS public.ix_human_approvals_run_id;
DROP INDEX IF EXISTS public.ix_feishu_message_deliveries_status_created_at;
DROP INDEX IF EXISTS public.ix_feishu_message_deliveries_run_id;
DROP INDEX IF EXISTS public.ix_feishu_field_mappings_resource_id;
DROP INDEX IF EXISTS public.ix_evidence_sets_run_id;
DROP INDEX IF EXISTS public.ix_evidence_sets_normalized_snapshot_id;
DROP INDEX IF EXISTS public.ix_evidence_sets_metric_snapshot_id;
DROP INDEX IF EXISTS public.ix_evidence_items_normalized_entity_id;
DROP INDEX IF EXISTS public.ix_evidence_items_evidence_set_id;
DROP INDEX IF EXISTS public.ix_encrypted_credentials_project_type_status;
DROP INDEX IF EXISTS public.ix_diagnosis_records_validation_result_id;
DROP INDEX IF EXISTS public.ix_diagnosis_records_run_id;
DROP INDEX IF EXISTS public.ix_diagnosis_records_run_created_at;
DROP INDEX IF EXISTS public.ix_callback_events_status_received_at;
DROP INDEX IF EXISTS public.ix_callback_events_run_id;
DROP INDEX IF EXISTS public.ix_audit_logs_run_occurred;
DROP INDEX IF EXISTS public.ix_audit_logs_run_id;
DROP INDEX IF EXISTS public.ix_audit_logs_actor_occurred;
DROP INDEX IF EXISTS public.ix_audit_logs_action_occurred;
DROP INDEX IF EXISTS public.ix_async_jobs_status_created;
ALTER TABLE IF EXISTS ONLY public.validation_results DROP CONSTRAINT IF EXISTS validation_results_pkey;
ALTER TABLE IF EXISTS ONLY public.validation_results DROP CONSTRAINT IF EXISTS uq_validation_results;
ALTER TABLE IF EXISTS ONLY public.tool_executions DROP CONSTRAINT IF EXISTS uq_tool_executions_attempt;
ALTER TABLE IF EXISTS ONLY public.source_data_batches DROP CONSTRAINT IF EXISTS uq_source_data_batches_identity;
ALTER TABLE IF EXISTS ONLY public.side_effect_operations DROP CONSTRAINT IF EXISTS uq_side_effect_operations_sequence;
ALTER TABLE IF EXISTS ONLY public.side_effect_operations DROP CONSTRAINT IF EXISTS uq_side_effect_operations_idempotency_key;
ALTER TABLE IF EXISTS ONLY public.side_effect_attempts DROP CONSTRAINT IF EXISTS uq_side_effect_attempts;
ALTER TABLE IF EXISTS ONLY public.report_versions DROP CONSTRAINT IF EXISTS uq_report_versions_version;
ALTER TABLE IF EXISTS ONLY public.report_versions DROP CONSTRAINT IF EXISTS uq_report_versions_content_hash;
ALTER TABLE IF EXISTS ONLY public.report_runs DROP CONSTRAINT IF EXISTS uq_report_runs_thread_id;
ALTER TABLE IF EXISTS ONLY public.report_runs DROP CONSTRAINT IF EXISTS uq_report_runs_project_period;
ALTER TABLE IF EXISTS ONLY public.report_evidence DROP CONSTRAINT IF EXISTS uq_report_evidence;
ALTER TABLE IF EXISTS ONLY public.report_claims DROP CONSTRAINT IF EXISTS uq_report_claims;
ALTER TABLE IF EXISTS ONLY public.report_artifacts DROP CONSTRAINT IF EXISTS uq_report_artifacts_operation;
ALTER TABLE IF EXISTS ONLY public.publish_plans DROP CONSTRAINT IF EXISTS uq_publish_plans_version;
ALTER TABLE IF EXISTS ONLY public.publish_plans DROP CONSTRAINT IF EXISTS uq_publish_plans_plan_hash;
ALTER TABLE IF EXISTS ONLY public.prompt_versions DROP CONSTRAINT IF EXISTS uq_prompt_versions_type_version;
ALTER TABLE IF EXISTS ONLY public.project_repositories DROP CONSTRAINT IF EXISTS uq_project_repo;
ALTER TABLE IF EXISTS ONLY public.outbox_messages DROP CONSTRAINT IF EXISTS uq_outbox_messages_dedupe_key;
ALTER TABLE IF EXISTS ONLY public.normalized_snapshots DROP CONSTRAINT IF EXISTS uq_normalized_snapshots;
ALTER TABLE IF EXISTS ONLY public.normalized_entities DROP CONSTRAINT IF EXISTS uq_normalized_entities_identity;
ALTER TABLE IF EXISTS ONLY public.node_executions DROP CONSTRAINT IF EXISTS uq_node_executions_attempt;
ALTER TABLE IF EXISTS ONLY public.model_configs DROP CONSTRAINT IF EXISTS uq_model_configs_scope;
ALTER TABLE IF EXISTS ONLY public.metric_snapshots DROP CONSTRAINT IF EXISTS uq_metric_snapshots;
ALTER TABLE IF EXISTS ONLY public.human_approvals DROP CONSTRAINT IF EXISTS uq_human_approvals_revision;
ALTER TABLE IF EXISTS ONLY public.human_approvals DROP CONSTRAINT IF EXISTS uq_human_approvals_challenge_id;
ALTER TABLE IF EXISTS ONLY public.feishu_resources DROP CONSTRAINT IF EXISTS uq_feishu_resource;
ALTER TABLE IF EXISTS ONLY public.feishu_message_deliveries DROP CONSTRAINT IF EXISTS uq_feishu_message_deliveries_run_purpose_revision_recipient;
ALTER TABLE IF EXISTS ONLY public.feishu_message_deliveries DROP CONSTRAINT IF EXISTS uq_feishu_message_deliveries_idempotency_key;
ALTER TABLE IF EXISTS ONLY public.feishu_field_mappings DROP CONSTRAINT IF EXISTS uq_feishu_field_mappings_logical;
ALTER TABLE IF EXISTS ONLY public.feishu_field_mappings DROP CONSTRAINT IF EXISTS uq_feishu_field_mappings_external;
ALTER TABLE IF EXISTS ONLY public.evidence_sets DROP CONSTRAINT IF EXISTS uq_evidence_sets;
ALTER TABLE IF EXISTS ONLY public.evidence_items DROP CONSTRAINT IF EXISTS uq_evidence_items;
ALTER TABLE IF EXISTS ONLY public.encrypted_credentials DROP CONSTRAINT IF EXISTS uq_encrypted_credentials_label;
ALTER TABLE IF EXISTS ONLY public.encrypted_credentials DROP CONSTRAINT IF EXISTS uq_encrypted_credentials_fingerprint;
ALTER TABLE IF EXISTS ONLY public.diagnosis_records DROP CONSTRAINT IF EXISTS uq_diagnosis_records_attempt;
ALTER TABLE IF EXISTS ONLY public.callback_events DROP CONSTRAINT IF EXISTS uq_callback_events_provider_event_id;
ALTER TABLE IF EXISTS ONLY public.async_jobs DROP CONSTRAINT IF EXISTS uq_async_jobs_request;
ALTER TABLE IF EXISTS ONLY public.tool_executions DROP CONSTRAINT IF EXISTS tool_executions_pkey;
ALTER TABLE IF EXISTS ONLY public.source_data_batches DROP CONSTRAINT IF EXISTS source_data_batches_pkey;
ALTER TABLE IF EXISTS ONLY public.side_effect_operations DROP CONSTRAINT IF EXISTS side_effect_operations_pkey;
ALTER TABLE IF EXISTS ONLY public.side_effect_attempts DROP CONSTRAINT IF EXISTS side_effect_attempts_pkey;
ALTER TABLE IF EXISTS ONLY public.run_status_history DROP CONSTRAINT IF EXISTS run_status_history_pkey;
ALTER TABLE IF EXISTS ONLY public.report_versions DROP CONSTRAINT IF EXISTS report_versions_pkey;
ALTER TABLE IF EXISTS ONLY public.report_runs DROP CONSTRAINT IF EXISTS report_runs_pkey;
ALTER TABLE IF EXISTS ONLY public.report_evidence DROP CONSTRAINT IF EXISTS report_evidence_pkey;
ALTER TABLE IF EXISTS ONLY public.report_claims DROP CONSTRAINT IF EXISTS report_claims_pkey;
ALTER TABLE IF EXISTS ONLY public.report_artifacts DROP CONSTRAINT IF EXISTS report_artifacts_pkey;
ALTER TABLE IF EXISTS ONLY public.publish_plans DROP CONSTRAINT IF EXISTS publish_plans_pkey;
ALTER TABLE IF EXISTS ONLY public.prompt_versions DROP CONSTRAINT IF EXISTS prompt_versions_pkey;
ALTER TABLE IF EXISTS ONLY public.projects DROP CONSTRAINT IF EXISTS projects_pkey;
ALTER TABLE IF EXISTS ONLY public.project_repositories DROP CONSTRAINT IF EXISTS project_repositories_pkey;
ALTER TABLE IF EXISTS ONLY public.outbox_messages DROP CONSTRAINT IF EXISTS outbox_messages_pkey;
ALTER TABLE IF EXISTS ONLY public.onboarding_sessions DROP CONSTRAINT IF EXISTS onboarding_sessions_pkey;
ALTER TABLE IF EXISTS ONLY public.normalized_snapshots DROP CONSTRAINT IF EXISTS normalized_snapshots_pkey;
ALTER TABLE IF EXISTS ONLY public.normalized_entities DROP CONSTRAINT IF EXISTS normalized_entities_pkey;
ALTER TABLE IF EXISTS ONLY public.node_executions DROP CONSTRAINT IF EXISTS node_executions_pkey;
ALTER TABLE IF EXISTS ONLY public.model_configs DROP CONSTRAINT IF EXISTS model_configs_pkey;
ALTER TABLE IF EXISTS ONLY public.metric_snapshots DROP CONSTRAINT IF EXISTS metric_snapshots_pkey;
ALTER TABLE IF EXISTS ONLY public.llm_executions DROP CONSTRAINT IF EXISTS llm_executions_pkey;
ALTER TABLE IF EXISTS ONLY public.human_approvals DROP CONSTRAINT IF EXISTS human_approvals_pkey;
ALTER TABLE IF EXISTS ONLY public.feishu_resources DROP CONSTRAINT IF EXISTS feishu_resources_pkey;
ALTER TABLE IF EXISTS ONLY public.feishu_message_deliveries DROP CONSTRAINT IF EXISTS feishu_message_deliveries_pkey;
ALTER TABLE IF EXISTS ONLY public.feishu_field_mappings DROP CONSTRAINT IF EXISTS feishu_field_mappings_pkey;
ALTER TABLE IF EXISTS ONLY public.evidence_sets DROP CONSTRAINT IF EXISTS evidence_sets_pkey;
ALTER TABLE IF EXISTS ONLY public.evidence_items DROP CONSTRAINT IF EXISTS evidence_items_pkey;
ALTER TABLE IF EXISTS ONLY public.encrypted_credentials DROP CONSTRAINT IF EXISTS encrypted_credentials_pkey;
ALTER TABLE IF EXISTS ONLY public.diagnosis_records DROP CONSTRAINT IF EXISTS diagnosis_records_pkey;
ALTER TABLE IF EXISTS ONLY public.callback_events DROP CONSTRAINT IF EXISTS callback_events_pkey;
ALTER TABLE IF EXISTS ONLY public.audit_logs DROP CONSTRAINT IF EXISTS audit_logs_pkey;
ALTER TABLE IF EXISTS ONLY public.async_jobs DROP CONSTRAINT IF EXISTS async_jobs_pkey;
ALTER TABLE IF EXISTS ONLY public.alembic_version DROP CONSTRAINT IF EXISTS alembic_version_pkc;
ALTER TABLE IF EXISTS public.run_status_history ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.callback_events ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.audit_logs ALTER COLUMN id DROP DEFAULT;
DROP TABLE IF EXISTS public.validation_results;
DROP TABLE IF EXISTS public.tool_executions;
DROP TABLE IF EXISTS public.source_data_batches;
DROP TABLE IF EXISTS public.side_effect_operations;
DROP TABLE IF EXISTS public.side_effect_attempts;
DROP SEQUENCE IF EXISTS public.run_status_history_id_seq;
DROP TABLE IF EXISTS public.run_status_history;
DROP TABLE IF EXISTS public.report_versions;
DROP TABLE IF EXISTS public.report_runs;
DROP TABLE IF EXISTS public.report_evidence;
DROP TABLE IF EXISTS public.report_claims;
DROP TABLE IF EXISTS public.report_artifacts;
DROP TABLE IF EXISTS public.publish_plans;
DROP TABLE IF EXISTS public.prompt_versions;
DROP TABLE IF EXISTS public.projects;
DROP TABLE IF EXISTS public.project_repositories;
DROP TABLE IF EXISTS public.outbox_messages;
DROP TABLE IF EXISTS public.onboarding_sessions;
DROP TABLE IF EXISTS public.normalized_snapshots;
DROP TABLE IF EXISTS public.normalized_entities;
DROP TABLE IF EXISTS public.node_executions;
DROP TABLE IF EXISTS public.model_configs;
DROP TABLE IF EXISTS public.metric_snapshots;
DROP TABLE IF EXISTS public.llm_executions;
DROP TABLE IF EXISTS public.human_approvals;
DROP TABLE IF EXISTS public.feishu_resources;
DROP TABLE IF EXISTS public.feishu_message_deliveries;
DROP TABLE IF EXISTS public.feishu_field_mappings;
DROP TABLE IF EXISTS public.evidence_sets;
DROP TABLE IF EXISTS public.evidence_items;
DROP TABLE IF EXISTS public.encrypted_credentials;
DROP TABLE IF EXISTS public.diagnosis_records;
DROP SEQUENCE IF EXISTS public.callback_events_id_seq;
DROP TABLE IF EXISTS public.callback_events;
DROP SEQUENCE IF EXISTS public.audit_logs_id_seq;
DROP TABLE IF EXISTS public.audit_logs;
DROP TABLE IF EXISTS public.async_jobs;
DROP TABLE IF EXISTS public.alembic_version;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: async_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.async_jobs (
    id character varying(36) NOT NULL,
    job_type character varying(64) NOT NULL,
    status character varying(24) NOT NULL,
    run_id character varying(36),
    requested_by character varying(128) NOT NULL,
    request_hash character varying(64) NOT NULL,
    result_summary json NOT NULL,
    error_code character varying(64),
    error_summary character varying(512),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    request_id character varying(128),
    run_id character varying(36),
    actor_type character varying(16) NOT NULL,
    actor_id character varying(128) NOT NULL,
    action character varying(64) NOT NULL,
    resource_type character varying(64) NOT NULL,
    resource_id character varying(128) NOT NULL,
    before_summary json NOT NULL,
    after_summary json NOT NULL,
    result character varying(24) NOT NULL,
    ip_hash character varying(128),
    metadata json NOT NULL
);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: callback_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.callback_events (
    id integer NOT NULL,
    provider character varying(32) NOT NULL,
    external_event_id character varying(256) NOT NULL,
    event_type character varying(64) NOT NULL,
    payload_hash character varying(64) NOT NULL,
    actor_id character varying(128) NOT NULL,
    run_id character varying(36),
    status character varying(24) NOT NULL,
    attempt_count integer NOT NULL,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    claimed_at timestamp with time zone,
    claimed_by character varying(128),
    lease_expires_at timestamp with time zone,
    next_attempt_at timestamp with time zone,
    processed_at timestamp with time zone,
    dead_lettered_at timestamp with time zone,
    last_error_class character varying(128),
    last_error_summary character varying(512)
);


--
-- Name: callback_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.callback_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: callback_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.callback_events_id_seq OWNED BY public.callback_events.id;


--
-- Name: diagnosis_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.diagnosis_records (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    validation_result_id character varying(36),
    problem_key character varying(128) NOT NULL,
    problem_type character varying(64) NOT NULL,
    severity character varying(24) NOT NULL,
    observation json NOT NULL,
    diagnosis json NOT NULL,
    impact_scope json NOT NULL,
    recoverability character varying(24) NOT NULL,
    planned_action character varying(64) NOT NULL,
    action_params json NOT NULL,
    attempt integer NOT NULL,
    result character varying(24) NOT NULL,
    next_node character varying(80),
    created_at timestamp with time zone NOT NULL,
    resolved_at timestamp with time zone
);


--
-- Name: encrypted_credentials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.encrypted_credentials (
    id character varying(36) NOT NULL,
    project_id character varying(36),
    credential_type character varying(32) NOT NULL,
    label character varying(128) NOT NULL,
    ciphertext bytea NOT NULL,
    nonce bytea NOT NULL,
    key_version character varying(32) NOT NULL,
    fingerprint character varying(64) NOT NULL,
    status character varying(24) NOT NULL,
    expires_at timestamp with time zone,
    last_validated_at timestamp with time zone,
    created_by character varying(128) NOT NULL,
    updated_by character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: evidence_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evidence_items (
    id character varying(36) NOT NULL,
    evidence_set_id character varying(36) NOT NULL,
    evidence_key character varying(128) NOT NULL,
    source_type character varying(24) NOT NULL,
    source_resource_id character varying(36) NOT NULL,
    external_id character varying(128) NOT NULL,
    url character varying(512),
    period_start timestamp with time zone,
    period_end timestamp with time zone,
    evidence_summary character varying(512),
    confidence double precision NOT NULL,
    normalized_entity_id character varying(36),
    content_hash character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: evidence_sets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evidence_sets (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    normalized_snapshot_id character varying(36) NOT NULL,
    metric_snapshot_id character varying(36) NOT NULL,
    builder_version character varying(32) NOT NULL,
    content_hash character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: feishu_field_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feishu_field_mappings (
    id character varying(36) NOT NULL,
    resource_id character varying(36) NOT NULL,
    logical_field character varying(128) NOT NULL,
    external_field_id character varying(128) NOT NULL,
    external_field_name character varying(256),
    external_field_type character varying(64),
    converter character varying(64),
    required_level character varying(16) NOT NULL,
    mapping_options json NOT NULL,
    enabled boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: feishu_message_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feishu_message_deliveries (
    id character varying(36) NOT NULL,
    run_id character varying(36),
    onboarding_session_id character varying(36),
    purpose character varying(64) NOT NULL,
    revision integer NOT NULL,
    recipient_type character varying(16) NOT NULL,
    recipient_id character varying(128) NOT NULL,
    content_hash character varying(64) NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    status character varying(24) NOT NULL,
    external_message_id character varying(256),
    attempt_count integer NOT NULL,
    last_error_summary character varying(512),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: feishu_resources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feishu_resources (
    id character varying(36) NOT NULL,
    project_id character varying(36) NOT NULL,
    resource_type character varying(64) NOT NULL,
    external_id character varying(300) NOT NULL,
    name character varying(256),
    schema_hash character varying(64),
    enabled boolean DEFAULT true NOT NULL,
    revision integer DEFAULT 1 NOT NULL,
    last_connectivity_status character varying(24),
    last_connectivity_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: human_approvals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.human_approvals (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    approval_type character varying(24) NOT NULL,
    revision integer NOT NULL,
    status character varying(24) DEFAULT 'pending'::character varying NOT NULL,
    challenge_id character varying(36) NOT NULL,
    card_message_id character varying(128),
    requested_from json NOT NULL,
    request_payload_hash character varying(64) NOT NULL,
    plan_hash character varying(64),
    actor_id character varying(128),
    actor_type character varying(16),
    decision character varying(32),
    supplement json,
    decided_at timestamp with time zone,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: llm_executions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_executions (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    node_execution_id character varying(36) NOT NULL,
    provider character varying(64) NOT NULL,
    model character varying(128) NOT NULL,
    prompt_type character varying(64) NOT NULL,
    prompt_version_id character varying(36),
    input_hash character varying(64) NOT NULL,
    output_ref character varying(256),
    status character varying(24) NOT NULL,
    schema_valid boolean DEFAULT false NOT NULL,
    input_tokens integer,
    output_tokens integer,
    total_tokens integer,
    duration_ms integer,
    error_class character varying(128),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: metric_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metric_snapshots (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    normalized_snapshot_id character varying(36) NOT NULL,
    definition_version character varying(32) NOT NULL,
    period_start timestamp with time zone NOT NULL,
    period_end timestamp with time zone NOT NULL,
    metrics jsonb NOT NULL,
    content_hash character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: model_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_configs (
    id character varying(36) NOT NULL,
    scope character varying(32) NOT NULL,
    base_url character varying(512),
    model character varying(128) NOT NULL,
    temperature double precision NOT NULL,
    timeout_seconds integer NOT NULL,
    max_retries integer NOT NULL,
    stream boolean NOT NULL,
    revision integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: node_executions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.node_executions (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    node_name character varying(80) NOT NULL,
    node_attempt integer NOT NULL,
    checkpoint_before character varying(256),
    checkpoint_after character varying(256),
    status character varying(20) NOT NULL,
    input_summary json NOT NULL,
    output_summary json NOT NULL,
    error_class character varying(128),
    error_summary character varying(512),
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    duration_ms integer
);


--
-- Name: normalized_entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.normalized_entities (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    normalized_snapshot_id character varying(36) NOT NULL,
    source_type character varying(24) NOT NULL,
    entity_type character varying(32) NOT NULL,
    source_resource_id character varying(36) NOT NULL,
    external_id character varying(128) NOT NULL,
    repository_id character varying(36),
    url character varying(512),
    title character varying(512),
    state character varying(32),
    author_external_id character varying(128),
    assignee_external_ids jsonb NOT NULL,
    labels jsonb NOT NULL,
    milestone_external_id character varying(128),
    created_at_external timestamp with time zone,
    updated_at_external timestamp with time zone,
    closed_at_external timestamp with time zone,
    occurred_at timestamp with time zone,
    raw_batch_id character varying(36),
    raw_summary character varying(512),
    attributes jsonb NOT NULL,
    content_hash character varying(64) NOT NULL,
    fetched_at timestamp with time zone NOT NULL
);


--
-- Name: normalized_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.normalized_snapshots (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    source_batch_set_hash character varying(64) NOT NULL,
    mapping_revision character varying(32) NOT NULL,
    normalizer_version character varying(32) NOT NULL,
    entity_count integer NOT NULL,
    status character varying(16) NOT NULL,
    content_hash character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: onboarding_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_sessions (
    id character varying(36) NOT NULL,
    feishu_actor_id character varying(128) NOT NULL,
    status character varying(24) NOT NULL,
    current_step character varying(64) NOT NULL,
    draft_config json NOT NULL,
    credential_ref character varying(36),
    card_message_id character varying(128),
    revision integer NOT NULL,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: outbox_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outbox_messages (
    id character varying(36) NOT NULL,
    topic character varying(128) NOT NULL,
    aggregate_type character varying(64) NOT NULL,
    aggregate_id character varying(128) NOT NULL,
    payload jsonb NOT NULL,
    dedupe_key character varying(64) NOT NULL,
    status character varying(24) NOT NULL,
    attempt_count integer NOT NULL,
    available_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    claimed_at timestamp with time zone,
    claimed_by character varying(128),
    lease_expires_at timestamp with time zone,
    provider_request_id character varying(256),
    external_message_id character varying(256),
    published_at timestamp with time zone,
    dead_lettered_at timestamp with time zone,
    last_error_class character varying(128),
    last_error_summary character varying(512)
);


--
-- Name: project_repositories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_repositories (
    id character varying(36) NOT NULL,
    project_id character varying(36) NOT NULL,
    external_id character varying(300) NOT NULL,
    provider character varying(32) NOT NULL,
    owner character varying(128),
    repo character varying(128),
    repository_type character varying(32),
    weight integer DEFAULT 100 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    default_branch character varying(128),
    last_connectivity_status character varying(24),
    last_connectivity_at timestamp with time zone,
    revision integer DEFAULT 1 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.projects (
    id character varying(36) NOT NULL,
    name character varying(200) NOT NULL,
    timezone character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    description character varying(512),
    default_period_rule json DEFAULT '{}'::json NOT NULL,
    default_prompt_version_id character varying(36),
    revision integer DEFAULT 1 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: prompt_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_versions (
    id character varying(36) NOT NULL,
    prompt_type character varying(32) NOT NULL,
    version integer NOT NULL,
    content text NOT NULL,
    content_hash character varying(64) NOT NULL,
    status character varying(16) NOT NULL,
    model_constraints json NOT NULL,
    created_by character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: publish_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.publish_plans (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    report_version_id character varying(36) NOT NULL,
    version integer NOT NULL,
    status character varying(32) NOT NULL,
    canonical_plan jsonb NOT NULL,
    plan_hash character varying(64) NOT NULL,
    content_version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    approved_at timestamp with time zone,
    invalidated_at timestamp with time zone
);


--
-- Name: report_artifacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_artifacts (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    report_version_id character varying(36) NOT NULL,
    artifact_type character varying(32) NOT NULL,
    operation_id character varying(36) NOT NULL,
    external_id character varying(256),
    url character varying(512),
    target_ref character varying(512) NOT NULL,
    content_hash character varying(64) NOT NULL,
    status character varying(24) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    verified_at timestamp with time zone
);


--
-- Name: report_claims; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_claims (
    id character varying(36) NOT NULL,
    report_version_id character varying(36) NOT NULL,
    claim_key character varying(128) NOT NULL,
    content character varying(1024) NOT NULL,
    claim_type character varying(24) NOT NULL,
    importance character varying(24) NOT NULL,
    period_start timestamp with time zone,
    period_end timestamp with time zone,
    confidence double precision NOT NULL,
    grounding_status character varying(24) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: report_evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_evidence (
    id character varying(36) NOT NULL,
    claim_id character varying(36) NOT NULL,
    evidence_item_id character varying(36) NOT NULL,
    citation_order integer NOT NULL,
    relevance_score double precision NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: report_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_runs (
    id character varying(36) NOT NULL,
    project_id character varying(36) NOT NULL,
    period_key character varying(120) NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    status character varying(32) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    thread_id character varying(128) NOT NULL,
    graph_version character varying(32) DEFAULT 'weekly_report.v1'::character varying NOT NULL,
    state_schema_version integer DEFAULT 1 NOT NULL,
    current_stage character varying(40) DEFAULT 'created'::character varying NOT NULL,
    current_node character varying(80),
    scope_revision integer DEFAULT 1 NOT NULL,
    approved_publish_plan_id character varying(36),
    lease_owner character varying(128),
    lease_expires_at timestamp with time zone,
    heartbeat_at timestamp with time zone,
    version integer DEFAULT 1 NOT NULL
);


--
-- Name: report_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_versions (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    version integer NOT NULL,
    status character varying(24) NOT NULL,
    structured_report jsonb NOT NULL,
    structured_hash character varying(64) NOT NULL,
    rendered_content text,
    content_hash character varying(64) NOT NULL,
    data_snapshot_hash character varying(64) NOT NULL,
    prompt_version_ids jsonb NOT NULL,
    model_info jsonb NOT NULL,
    confidence double precision NOT NULL,
    data_quality_status character varying(24) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    verified_at timestamp with time zone
);


--
-- Name: run_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.run_status_history (
    id integer NOT NULL,
    run_id character varying(36) NOT NULL,
    from_status character varying(40) NOT NULL,
    to_status character varying(40) NOT NULL,
    reason_code character varying(64) NOT NULL,
    actor_type character varying(16) NOT NULL,
    actor_id character varying(128) NOT NULL,
    node_name character varying(80),
    checkpoint_ref character varying(256),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: run_status_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.run_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: run_status_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.run_status_history_id_seq OWNED BY public.run_status_history.id;


--
-- Name: side_effect_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.side_effect_attempts (
    id character varying(36) NOT NULL,
    operation_id character varying(36) NOT NULL,
    attempt integer NOT NULL,
    status character varying(24) NOT NULL,
    request_summary jsonb NOT NULL,
    provider_request_id character varying(256),
    response_summary jsonb NOT NULL,
    error_class character varying(128),
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone
);


--
-- Name: side_effect_operations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.side_effect_operations (
    id character varying(36) NOT NULL,
    publish_plan_id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    sequence integer NOT NULL,
    operation_type character varying(64) NOT NULL,
    target_ref character varying(512) NOT NULL,
    target_hash character varying(64) NOT NULL,
    payload_ref character varying(512) NOT NULL,
    payload_hash character varying(64) NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    status character varying(24) NOT NULL,
    attempt_count integer NOT NULL,
    external_resource_id character varying(256),
    external_url character varying(512),
    provider_request_id character varying(256),
    verification_status character varying(24),
    last_error_class character varying(128),
    last_error_summary character varying(512),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    version integer NOT NULL,
    lease_owner character varying(128),
    lease_expires_at timestamp with time zone,
    heartbeat_at timestamp with time zone
);


--
-- Name: source_data_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_data_batches (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    source_type character varying(24) NOT NULL,
    source_resource_id character varying(36) NOT NULL,
    entity_type character varying(32) NOT NULL,
    page_no integer NOT NULL,
    cursor character varying(512),
    period_start timestamp with time zone,
    period_end timestamp with time zone,
    payload jsonb NOT NULL,
    payload_hash character varying(64) NOT NULL,
    record_count integer NOT NULL,
    schema_version character varying(32) NOT NULL,
    fetch_status character varying(20) NOT NULL,
    fetched_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone
);


--
-- Name: tool_executions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tool_executions (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    node_execution_id character varying(128) NOT NULL,
    tool_name character varying(128) NOT NULL,
    tool_version character varying(32) NOT NULL,
    attempt integer NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    request_summary jsonb NOT NULL,
    result_summary jsonb NOT NULL,
    data_ref character varying(36),
    provider_request_id character varying(256),
    status character varying(24) NOT NULL,
    error_class character varying(128),
    error_code character varying(64),
    retryable boolean DEFAULT false NOT NULL,
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    duration_ms integer
);


--
-- Name: validation_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.validation_results (
    id character varying(36) NOT NULL,
    run_id character varying(36) NOT NULL,
    validation_pass boolean DEFAULT false NOT NULL,
    data_quality_status character varying(24) NOT NULL,
    rule_set_version character varying(32) NOT NULL,
    critical_count integer NOT NULL,
    warning_count integer NOT NULL,
    missing_items jsonb NOT NULL,
    conflicts jsonb NOT NULL,
    warnings jsonb NOT NULL,
    input_snapshot_hash character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: callback_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.callback_events ALTER COLUMN id SET DEFAULT nextval('public.callback_events_id_seq'::regclass);


--
-- Name: run_status_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_status_history ALTER COLUMN id SET DEFAULT nextval('public.run_status_history_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
t42_run_leases_lifecycle
\.


--
-- Data for Name: async_jobs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.async_jobs (id, job_type, status, run_id, requested_by, request_hash, result_summary, error_code, error_summary, created_at, started_at, completed_at) FROM stdin;
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_logs (id, occurred_at, request_id, run_id, actor_type, actor_id, action, resource_type, resource_id, before_summary, after_summary, result, ip_hash, metadata) FROM stdin;
\.


--
-- Data for Name: callback_events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.callback_events (id, provider, external_event_id, event_type, payload_hash, actor_id, run_id, status, attempt_count, received_at, claimed_at, claimed_by, lease_expires_at, next_attempt_at, processed_at, dead_lettered_at, last_error_class, last_error_summary) FROM stdin;
\.


--
-- Data for Name: diagnosis_records; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.diagnosis_records (id, run_id, validation_result_id, problem_key, problem_type, severity, observation, diagnosis, impact_scope, recoverability, planned_action, action_params, attempt, result, next_node, created_at, resolved_at) FROM stdin;
\.


--
-- Data for Name: encrypted_credentials; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.encrypted_credentials (id, project_id, credential_type, label, ciphertext, nonce, key_version, fingerprint, status, expires_at, last_validated_at, created_by, updated_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: evidence_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.evidence_items (id, evidence_set_id, evidence_key, source_type, source_resource_id, external_id, url, period_start, period_end, evidence_summary, confidence, normalized_entity_id, content_hash, created_at) FROM stdin;
\.


--
-- Data for Name: evidence_sets; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.evidence_sets (id, run_id, normalized_snapshot_id, metric_snapshot_id, builder_version, content_hash, created_at) FROM stdin;
\.


--
-- Data for Name: feishu_field_mappings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.feishu_field_mappings (id, resource_id, logical_field, external_field_id, external_field_name, external_field_type, converter, required_level, mapping_options, enabled, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: feishu_message_deliveries; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.feishu_message_deliveries (id, run_id, onboarding_session_id, purpose, revision, recipient_type, recipient_id, content_hash, idempotency_key, status, external_message_id, attempt_count, last_error_summary, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: feishu_resources; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.feishu_resources (id, project_id, resource_type, external_id, name, schema_hash, enabled, revision, last_connectivity_status, last_connectivity_at, updated_at) FROM stdin;
\.


--
-- Data for Name: human_approvals; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.human_approvals (id, run_id, approval_type, revision, status, challenge_id, card_message_id, requested_from, request_payload_hash, plan_hash, actor_id, actor_type, decision, supplement, decided_at, expires_at, created_at) FROM stdin;
\.


--
-- Data for Name: llm_executions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.llm_executions (id, run_id, node_execution_id, provider, model, prompt_type, prompt_version_id, input_hash, output_ref, status, schema_valid, input_tokens, output_tokens, total_tokens, duration_ms, error_class, created_at) FROM stdin;
\.


--
-- Data for Name: metric_snapshots; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.metric_snapshots (id, run_id, normalized_snapshot_id, definition_version, period_start, period_end, metrics, content_hash, created_at) FROM stdin;
\.


--
-- Data for Name: model_configs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.model_configs (id, scope, base_url, model, temperature, timeout_seconds, max_retries, stream, revision, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: node_executions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.node_executions (id, run_id, node_name, node_attempt, checkpoint_before, checkpoint_after, status, input_summary, output_summary, error_class, error_summary, started_at, ended_at, duration_ms) FROM stdin;
\.


--
-- Data for Name: normalized_entities; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.normalized_entities (id, run_id, normalized_snapshot_id, source_type, entity_type, source_resource_id, external_id, repository_id, url, title, state, author_external_id, assignee_external_ids, labels, milestone_external_id, created_at_external, updated_at_external, closed_at_external, occurred_at, raw_batch_id, raw_summary, attributes, content_hash, fetched_at) FROM stdin;
\.


--
-- Data for Name: normalized_snapshots; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.normalized_snapshots (id, run_id, source_batch_set_hash, mapping_revision, normalizer_version, entity_count, status, content_hash, created_at) FROM stdin;
\.


--
-- Data for Name: onboarding_sessions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.onboarding_sessions (id, feishu_actor_id, status, current_step, draft_config, credential_ref, card_message_id, revision, expires_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: outbox_messages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.outbox_messages (id, topic, aggregate_type, aggregate_id, payload, dedupe_key, status, attempt_count, available_at, created_at, claimed_at, claimed_by, lease_expires_at, provider_request_id, external_message_id, published_at, dead_lettered_at, last_error_class, last_error_summary) FROM stdin;
\.


--
-- Data for Name: project_repositories; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.project_repositories (id, project_id, external_id, provider, owner, repo, repository_type, weight, enabled, default_branch, last_connectivity_status, last_connectivity_at, revision, updated_at) FROM stdin;
\.


--
-- Data for Name: projects; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.projects (id, name, timezone, created_at, description, default_period_rule, default_prompt_version_id, revision, updated_at) FROM stdin;
0f7b44ec-7994-423d-87d5-5df65af48095	Recovery Drill	Asia/Shanghai	2026-07-31 10:01:05.396594+00	\N	{}	\N	1	2026-07-31 10:01:05.396594+00
\.


--
-- Data for Name: prompt_versions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.prompt_versions (id, prompt_type, version, content, content_hash, status, model_constraints, created_by, created_at) FROM stdin;
\.


--
-- Data for Name: publish_plans; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.publish_plans (id, run_id, report_version_id, version, status, canonical_plan, plan_hash, content_version, created_at, approved_at, invalidated_at) FROM stdin;
\.


--
-- Data for Name: report_artifacts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.report_artifacts (id, run_id, report_version_id, artifact_type, operation_id, external_id, url, target_ref, content_hash, status, created_at, verified_at) FROM stdin;
\.


--
-- Data for Name: report_claims; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.report_claims (id, report_version_id, claim_key, content, claim_type, importance, period_start, period_end, confidence, grounding_status, created_at) FROM stdin;
\.


--
-- Data for Name: report_evidence; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.report_evidence (id, claim_id, evidence_item_id, citation_order, relevance_score, created_at) FROM stdin;
\.


--
-- Data for Name: report_runs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.report_runs (id, project_id, period_key, period_start, period_end, status, created_at, thread_id, graph_version, state_schema_version, current_stage, current_node, scope_revision, approved_publish_plan_id, lease_owner, lease_expires_at, heartbeat_at, version) FROM stdin;
50a73aa6-9f19-4103-a3a1-1c0b78baa45e	0f7b44ec-7994-423d-87d5-5df65af48095	2026-W31	2026-07-27	2026-08-03	created	2026-07-31 10:01:05.396594+00	report-run:50a73aa6-9f19-4103-a3a1-1c0b78baa45e	weekly_report.v1	1	created	\N	1	\N	\N	\N	\N	1
\.


--
-- Data for Name: report_versions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.report_versions (id, run_id, version, status, structured_report, structured_hash, rendered_content, content_hash, data_snapshot_hash, prompt_version_ids, model_info, confidence, data_quality_status, created_at, verified_at) FROM stdin;
\.


--
-- Data for Name: run_status_history; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.run_status_history (id, run_id, from_status, to_status, reason_code, actor_type, actor_id, node_name, checkpoint_ref, created_at) FROM stdin;
\.


--
-- Data for Name: side_effect_attempts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.side_effect_attempts (id, operation_id, attempt, status, request_summary, provider_request_id, response_summary, error_class, started_at, ended_at) FROM stdin;
\.


--
-- Data for Name: side_effect_operations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.side_effect_operations (id, publish_plan_id, run_id, sequence, operation_type, target_ref, target_hash, payload_ref, payload_hash, idempotency_key, status, attempt_count, external_resource_id, external_url, provider_request_id, verification_status, last_error_class, last_error_summary, started_at, completed_at, updated_at, version, lease_owner, lease_expires_at, heartbeat_at) FROM stdin;
\.


--
-- Data for Name: source_data_batches; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.source_data_batches (id, run_id, source_type, source_resource_id, entity_type, page_no, cursor, period_start, period_end, payload, payload_hash, record_count, schema_version, fetch_status, fetched_at, expires_at) FROM stdin;
\.


--
-- Data for Name: tool_executions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tool_executions (id, run_id, node_execution_id, tool_name, tool_version, attempt, idempotency_key, request_summary, result_summary, data_ref, provider_request_id, status, error_class, error_code, retryable, started_at, ended_at, duration_ms) FROM stdin;
\.


--
-- Data for Name: validation_results; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.validation_results (id, run_id, validation_pass, data_quality_status, rule_set_version, critical_count, warning_count, missing_items, conflicts, warnings, input_snapshot_hash, created_at) FROM stdin;
\.


--
-- Name: audit_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.audit_logs_id_seq', 1, false);


--
-- Name: callback_events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.callback_events_id_seq', 1, false);


--
-- Name: run_status_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.run_status_history_id_seq', 1, false);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: async_jobs async_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.async_jobs
    ADD CONSTRAINT async_jobs_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: callback_events callback_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.callback_events
    ADD CONSTRAINT callback_events_pkey PRIMARY KEY (id);


--
-- Name: diagnosis_records diagnosis_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnosis_records
    ADD CONSTRAINT diagnosis_records_pkey PRIMARY KEY (id);


--
-- Name: encrypted_credentials encrypted_credentials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_credentials
    ADD CONSTRAINT encrypted_credentials_pkey PRIMARY KEY (id);


--
-- Name: evidence_items evidence_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_pkey PRIMARY KEY (id);


--
-- Name: evidence_sets evidence_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_sets
    ADD CONSTRAINT evidence_sets_pkey PRIMARY KEY (id);


--
-- Name: feishu_field_mappings feishu_field_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_field_mappings
    ADD CONSTRAINT feishu_field_mappings_pkey PRIMARY KEY (id);


--
-- Name: feishu_message_deliveries feishu_message_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_message_deliveries
    ADD CONSTRAINT feishu_message_deliveries_pkey PRIMARY KEY (id);


--
-- Name: feishu_resources feishu_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_resources
    ADD CONSTRAINT feishu_resources_pkey PRIMARY KEY (id);


--
-- Name: human_approvals human_approvals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_approvals
    ADD CONSTRAINT human_approvals_pkey PRIMARY KEY (id);


--
-- Name: llm_executions llm_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_executions
    ADD CONSTRAINT llm_executions_pkey PRIMARY KEY (id);


--
-- Name: metric_snapshots metric_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_snapshots
    ADD CONSTRAINT metric_snapshots_pkey PRIMARY KEY (id);


--
-- Name: model_configs model_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_configs
    ADD CONSTRAINT model_configs_pkey PRIMARY KEY (id);


--
-- Name: node_executions node_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.node_executions
    ADD CONSTRAINT node_executions_pkey PRIMARY KEY (id);


--
-- Name: normalized_entities normalized_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.normalized_entities
    ADD CONSTRAINT normalized_entities_pkey PRIMARY KEY (id);


--
-- Name: normalized_snapshots normalized_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.normalized_snapshots
    ADD CONSTRAINT normalized_snapshots_pkey PRIMARY KEY (id);


--
-- Name: onboarding_sessions onboarding_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_sessions
    ADD CONSTRAINT onboarding_sessions_pkey PRIMARY KEY (id);


--
-- Name: outbox_messages outbox_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outbox_messages
    ADD CONSTRAINT outbox_messages_pkey PRIMARY KEY (id);


--
-- Name: project_repositories project_repositories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_repositories
    ADD CONSTRAINT project_repositories_pkey PRIMARY KEY (id);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: prompt_versions prompt_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_versions
    ADD CONSTRAINT prompt_versions_pkey PRIMARY KEY (id);


--
-- Name: publish_plans publish_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publish_plans
    ADD CONSTRAINT publish_plans_pkey PRIMARY KEY (id);


--
-- Name: report_artifacts report_artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_pkey PRIMARY KEY (id);


--
-- Name: report_claims report_claims_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_claims
    ADD CONSTRAINT report_claims_pkey PRIMARY KEY (id);


--
-- Name: report_evidence report_evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_evidence
    ADD CONSTRAINT report_evidence_pkey PRIMARY KEY (id);


--
-- Name: report_runs report_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_runs
    ADD CONSTRAINT report_runs_pkey PRIMARY KEY (id);


--
-- Name: report_versions report_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_versions
    ADD CONSTRAINT report_versions_pkey PRIMARY KEY (id);


--
-- Name: run_status_history run_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_status_history
    ADD CONSTRAINT run_status_history_pkey PRIMARY KEY (id);


--
-- Name: side_effect_attempts side_effect_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effect_attempts
    ADD CONSTRAINT side_effect_attempts_pkey PRIMARY KEY (id);


--
-- Name: side_effect_operations side_effect_operations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effect_operations
    ADD CONSTRAINT side_effect_operations_pkey PRIMARY KEY (id);


--
-- Name: source_data_batches source_data_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_data_batches
    ADD CONSTRAINT source_data_batches_pkey PRIMARY KEY (id);


--
-- Name: tool_executions tool_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tool_executions
    ADD CONSTRAINT tool_executions_pkey PRIMARY KEY (id);


--
-- Name: async_jobs uq_async_jobs_request; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.async_jobs
    ADD CONSTRAINT uq_async_jobs_request UNIQUE (job_type, requested_by, request_hash);


--
-- Name: callback_events uq_callback_events_provider_event_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.callback_events
    ADD CONSTRAINT uq_callback_events_provider_event_id UNIQUE (provider, external_event_id);


--
-- Name: diagnosis_records uq_diagnosis_records_attempt; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnosis_records
    ADD CONSTRAINT uq_diagnosis_records_attempt UNIQUE (run_id, problem_key, attempt);


--
-- Name: encrypted_credentials uq_encrypted_credentials_fingerprint; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_credentials
    ADD CONSTRAINT uq_encrypted_credentials_fingerprint UNIQUE (fingerprint);


--
-- Name: encrypted_credentials uq_encrypted_credentials_label; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_credentials
    ADD CONSTRAINT uq_encrypted_credentials_label UNIQUE (project_id, credential_type, label);


--
-- Name: evidence_items uq_evidence_items; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT uq_evidence_items UNIQUE (evidence_set_id, evidence_key);


--
-- Name: evidence_sets uq_evidence_sets; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_sets
    ADD CONSTRAINT uq_evidence_sets UNIQUE (run_id, content_hash);


--
-- Name: feishu_field_mappings uq_feishu_field_mappings_external; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_field_mappings
    ADD CONSTRAINT uq_feishu_field_mappings_external UNIQUE (resource_id, external_field_id);


--
-- Name: feishu_field_mappings uq_feishu_field_mappings_logical; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_field_mappings
    ADD CONSTRAINT uq_feishu_field_mappings_logical UNIQUE (resource_id, logical_field);


--
-- Name: feishu_message_deliveries uq_feishu_message_deliveries_idempotency_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_message_deliveries
    ADD CONSTRAINT uq_feishu_message_deliveries_idempotency_key UNIQUE (idempotency_key);


--
-- Name: feishu_message_deliveries uq_feishu_message_deliveries_run_purpose_revision_recipient; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_message_deliveries
    ADD CONSTRAINT uq_feishu_message_deliveries_run_purpose_revision_recipient UNIQUE (run_id, purpose, revision, recipient_type, recipient_id);


--
-- Name: feishu_resources uq_feishu_resource; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_resources
    ADD CONSTRAINT uq_feishu_resource UNIQUE (project_id, resource_type);


--
-- Name: human_approvals uq_human_approvals_challenge_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_approvals
    ADD CONSTRAINT uq_human_approvals_challenge_id UNIQUE (challenge_id);


--
-- Name: human_approvals uq_human_approvals_revision; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_approvals
    ADD CONSTRAINT uq_human_approvals_revision UNIQUE (run_id, approval_type, revision);


--
-- Name: metric_snapshots uq_metric_snapshots; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_snapshots
    ADD CONSTRAINT uq_metric_snapshots UNIQUE (run_id, normalized_snapshot_id, definition_version, content_hash);


--
-- Name: model_configs uq_model_configs_scope; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_configs
    ADD CONSTRAINT uq_model_configs_scope UNIQUE (scope);


--
-- Name: node_executions uq_node_executions_attempt; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.node_executions
    ADD CONSTRAINT uq_node_executions_attempt UNIQUE (run_id, node_name, node_attempt);


--
-- Name: normalized_entities uq_normalized_entities_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.normalized_entities
    ADD CONSTRAINT uq_normalized_entities_identity UNIQUE (run_id, source_type, source_resource_id, entity_type, external_id, content_hash);


--
-- Name: normalized_snapshots uq_normalized_snapshots; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.normalized_snapshots
    ADD CONSTRAINT uq_normalized_snapshots UNIQUE (run_id, content_hash);


--
-- Name: outbox_messages uq_outbox_messages_dedupe_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outbox_messages
    ADD CONSTRAINT uq_outbox_messages_dedupe_key UNIQUE (dedupe_key);


--
-- Name: project_repositories uq_project_repo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_repositories
    ADD CONSTRAINT uq_project_repo UNIQUE (project_id, provider, external_id);


--
-- Name: prompt_versions uq_prompt_versions_type_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_versions
    ADD CONSTRAINT uq_prompt_versions_type_version UNIQUE (prompt_type, version);


--
-- Name: publish_plans uq_publish_plans_plan_hash; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publish_plans
    ADD CONSTRAINT uq_publish_plans_plan_hash UNIQUE (run_id, plan_hash);


--
-- Name: publish_plans uq_publish_plans_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publish_plans
    ADD CONSTRAINT uq_publish_plans_version UNIQUE (run_id, version);


--
-- Name: report_artifacts uq_report_artifacts_operation; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT uq_report_artifacts_operation UNIQUE (operation_id);


--
-- Name: report_claims uq_report_claims; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_claims
    ADD CONSTRAINT uq_report_claims UNIQUE (report_version_id, claim_key);


--
-- Name: report_evidence uq_report_evidence; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_evidence
    ADD CONSTRAINT uq_report_evidence UNIQUE (claim_id, evidence_item_id);


--
-- Name: report_runs uq_report_runs_project_period; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_runs
    ADD CONSTRAINT uq_report_runs_project_period UNIQUE (project_id, period_key);


--
-- Name: report_runs uq_report_runs_thread_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_runs
    ADD CONSTRAINT uq_report_runs_thread_id UNIQUE (thread_id);


--
-- Name: report_versions uq_report_versions_content_hash; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_versions
    ADD CONSTRAINT uq_report_versions_content_hash UNIQUE (run_id, content_hash);


--
-- Name: report_versions uq_report_versions_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_versions
    ADD CONSTRAINT uq_report_versions_version UNIQUE (run_id, version);


--
-- Name: side_effect_attempts uq_side_effect_attempts; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effect_attempts
    ADD CONSTRAINT uq_side_effect_attempts UNIQUE (operation_id, attempt);


--
-- Name: side_effect_operations uq_side_effect_operations_idempotency_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effect_operations
    ADD CONSTRAINT uq_side_effect_operations_idempotency_key UNIQUE (idempotency_key);


--
-- Name: side_effect_operations uq_side_effect_operations_sequence; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effect_operations
    ADD CONSTRAINT uq_side_effect_operations_sequence UNIQUE (publish_plan_id, sequence);


--
-- Name: source_data_batches uq_source_data_batches_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_data_batches
    ADD CONSTRAINT uq_source_data_batches_identity UNIQUE (run_id, source_type, source_resource_id, entity_type, page_no, payload_hash);


--
-- Name: tool_executions uq_tool_executions_attempt; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tool_executions
    ADD CONSTRAINT uq_tool_executions_attempt UNIQUE (run_id, idempotency_key, attempt);


--
-- Name: validation_results uq_validation_results; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.validation_results
    ADD CONSTRAINT uq_validation_results UNIQUE (run_id, input_snapshot_hash);


--
-- Name: validation_results validation_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.validation_results
    ADD CONSTRAINT validation_results_pkey PRIMARY KEY (id);


--
-- Name: ix_async_jobs_status_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_async_jobs_status_created ON public.async_jobs USING btree (status, created_at);


--
-- Name: ix_audit_logs_action_occurred; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_action_occurred ON public.audit_logs USING btree (action, occurred_at);


--
-- Name: ix_audit_logs_actor_occurred; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_actor_occurred ON public.audit_logs USING btree (actor_id, occurred_at);


--
-- Name: ix_audit_logs_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_run_id ON public.audit_logs USING btree (run_id);


--
-- Name: ix_audit_logs_run_occurred; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_run_occurred ON public.audit_logs USING btree (run_id, occurred_at);


--
-- Name: ix_callback_events_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_callback_events_run_id ON public.callback_events USING btree (run_id);


--
-- Name: ix_callback_events_status_received_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_callback_events_status_received_at ON public.callback_events USING btree (status, received_at);


--
-- Name: ix_diagnosis_records_run_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_diagnosis_records_run_created_at ON public.diagnosis_records USING btree (run_id, created_at);


--
-- Name: ix_diagnosis_records_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_diagnosis_records_run_id ON public.diagnosis_records USING btree (run_id);


--
-- Name: ix_diagnosis_records_validation_result_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_diagnosis_records_validation_result_id ON public.diagnosis_records USING btree (validation_result_id);


--
-- Name: ix_encrypted_credentials_project_type_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_encrypted_credentials_project_type_status ON public.encrypted_credentials USING btree (project_id, credential_type, status);


--
-- Name: ix_evidence_items_evidence_set_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_items_evidence_set_id ON public.evidence_items USING btree (evidence_set_id);


--
-- Name: ix_evidence_items_normalized_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_items_normalized_entity_id ON public.evidence_items USING btree (normalized_entity_id);


--
-- Name: ix_evidence_sets_metric_snapshot_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_sets_metric_snapshot_id ON public.evidence_sets USING btree (metric_snapshot_id);


--
-- Name: ix_evidence_sets_normalized_snapshot_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_sets_normalized_snapshot_id ON public.evidence_sets USING btree (normalized_snapshot_id);


--
-- Name: ix_evidence_sets_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_sets_run_id ON public.evidence_sets USING btree (run_id);


--
-- Name: ix_feishu_field_mappings_resource_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_feishu_field_mappings_resource_id ON public.feishu_field_mappings USING btree (resource_id);


--
-- Name: ix_feishu_message_deliveries_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_feishu_message_deliveries_run_id ON public.feishu_message_deliveries USING btree (run_id);


--
-- Name: ix_feishu_message_deliveries_status_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_feishu_message_deliveries_status_created_at ON public.feishu_message_deliveries USING btree (status, created_at);


--
-- Name: ix_human_approvals_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_human_approvals_run_id ON public.human_approvals USING btree (run_id);


--
-- Name: ix_llm_executions_node_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_llm_executions_node_created_at ON public.llm_executions USING btree (node_execution_id, created_at);


--
-- Name: ix_llm_executions_node_execution_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_llm_executions_node_execution_id ON public.llm_executions USING btree (node_execution_id);


--
-- Name: ix_llm_executions_run_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_llm_executions_run_created_at ON public.llm_executions USING btree (run_id, created_at);


--
-- Name: ix_llm_executions_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_llm_executions_run_id ON public.llm_executions USING btree (run_id);


--
-- Name: ix_metric_snapshots_normalized_snapshot_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_metric_snapshots_normalized_snapshot_id ON public.metric_snapshots USING btree (normalized_snapshot_id);


--
-- Name: ix_metric_snapshots_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_metric_snapshots_run_id ON public.metric_snapshots USING btree (run_id);


--
-- Name: ix_node_executions_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_executions_run_id ON public.node_executions USING btree (run_id);


--
-- Name: ix_node_executions_run_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_executions_run_started ON public.node_executions USING btree (run_id, started_at);


--
-- Name: ix_normalized_entities_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_normalized_entities_run_id ON public.normalized_entities USING btree (run_id);


--
-- Name: ix_normalized_entities_snapshot; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_normalized_entities_snapshot ON public.normalized_entities USING btree (normalized_snapshot_id);


--
-- Name: ix_normalized_snapshots_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_normalized_snapshots_run_id ON public.normalized_snapshots USING btree (run_id);


--
-- Name: ix_onboarding_sessions_actor_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_sessions_actor_status ON public.onboarding_sessions USING btree (feishu_actor_id, status);


--
-- Name: ix_onboarding_sessions_credential_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_sessions_credential_ref ON public.onboarding_sessions USING btree (credential_ref);


--
-- Name: ix_outbox_messages_status_available_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_outbox_messages_status_available_at ON public.outbox_messages USING btree (status, available_at);


--
-- Name: ix_outbox_messages_topic; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_outbox_messages_topic ON public.outbox_messages USING btree (topic);


--
-- Name: ix_prompt_versions_type_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_versions_type_status ON public.prompt_versions USING btree (prompt_type, status);


--
-- Name: ix_publish_plans_report_version_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_publish_plans_report_version_id ON public.publish_plans USING btree (report_version_id);


--
-- Name: ix_publish_plans_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_publish_plans_run_id ON public.publish_plans USING btree (run_id);


--
-- Name: ix_report_artifacts_operation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_artifacts_operation_id ON public.report_artifacts USING btree (operation_id);


--
-- Name: ix_report_artifacts_report_version_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_artifacts_report_version_id ON public.report_artifacts USING btree (report_version_id);


--
-- Name: ix_report_artifacts_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_artifacts_run_id ON public.report_artifacts USING btree (run_id);


--
-- Name: ix_report_artifacts_run_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_artifacts_run_type ON public.report_artifacts USING btree (run_id, artifact_type);


--
-- Name: ix_report_claims_report_version_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_claims_report_version_id ON public.report_claims USING btree (report_version_id);


--
-- Name: ix_report_evidence_claim_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_evidence_claim_id ON public.report_evidence USING btree (claim_id);


--
-- Name: ix_report_evidence_claim_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_evidence_claim_order ON public.report_evidence USING btree (claim_id, citation_order);


--
-- Name: ix_report_evidence_evidence_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_evidence_evidence_item_id ON public.report_evidence USING btree (evidence_item_id);


--
-- Name: ix_report_runs_approved_publish_plan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_runs_approved_publish_plan_id ON public.report_runs USING btree (approved_publish_plan_id);


--
-- Name: ix_report_runs_status_lease_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_runs_status_lease_expires_at ON public.report_runs USING btree (status, lease_expires_at);


--
-- Name: ix_report_versions_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_versions_run_id ON public.report_versions USING btree (run_id);


--
-- Name: ix_run_status_history_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_run_status_history_run_id ON public.run_status_history USING btree (run_id);


--
-- Name: ix_side_effect_attempts_operation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_side_effect_attempts_operation_id ON public.side_effect_attempts USING btree (operation_id);


--
-- Name: ix_side_effect_operations_publish_plan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_side_effect_operations_publish_plan_id ON public.side_effect_operations USING btree (publish_plan_id);


--
-- Name: ix_side_effect_operations_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_side_effect_operations_run_id ON public.side_effect_operations USING btree (run_id);


--
-- Name: ix_side_effect_operations_run_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_side_effect_operations_run_status ON public.side_effect_operations USING btree (run_id, status);


--
-- Name: ix_side_effect_operations_status_lease_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_side_effect_operations_status_lease_expires_at ON public.side_effect_operations USING btree (status, lease_expires_at);


--
-- Name: ix_source_data_batches_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_source_data_batches_expires_at ON public.source_data_batches USING btree (expires_at);


--
-- Name: ix_source_data_batches_run_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_source_data_batches_run_entity ON public.source_data_batches USING btree (run_id, entity_type);


--
-- Name: ix_source_data_batches_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_source_data_batches_run_id ON public.source_data_batches USING btree (run_id);


--
-- Name: ix_tool_executions_node_execution_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_executions_node_execution_id ON public.tool_executions USING btree (node_execution_id);


--
-- Name: ix_tool_executions_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_executions_run_id ON public.tool_executions USING btree (run_id);


--
-- Name: ix_tool_executions_run_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_executions_run_started ON public.tool_executions USING btree (run_id, started_at);


--
-- Name: ix_tool_executions_tool_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_executions_tool_status ON public.tool_executions USING btree (tool_name, status);


--
-- Name: ix_tool_executions_tool_status_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_executions_tool_status_started ON public.tool_executions USING btree (tool_name, status, started_at);


--
-- Name: ix_validation_results_run_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_validation_results_run_created ON public.validation_results USING btree (run_id, created_at);


--
-- Name: uq_onboarding_sessions_active_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_onboarding_sessions_active_actor ON public.onboarding_sessions USING btree (feishu_actor_id) WHERE ((status)::text = ANY ((ARRAY['in_progress'::character varying, 'pending_confirmation'::character varying])::text[]));


--
-- Name: async_jobs async_jobs_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.async_jobs
    ADD CONSTRAINT async_jobs_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE SET NULL;


--
-- Name: audit_logs audit_logs_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: callback_events callback_events_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.callback_events
    ADD CONSTRAINT callback_events_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: diagnosis_records diagnosis_records_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnosis_records
    ADD CONSTRAINT diagnosis_records_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: diagnosis_records diagnosis_records_validation_result_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diagnosis_records
    ADD CONSTRAINT diagnosis_records_validation_result_id_fkey FOREIGN KEY (validation_result_id) REFERENCES public.validation_results(id) ON DELETE SET NULL;


--
-- Name: encrypted_credentials encrypted_credentials_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_credentials
    ADD CONSTRAINT encrypted_credentials_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: evidence_items evidence_items_evidence_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_evidence_set_id_fkey FOREIGN KEY (evidence_set_id) REFERENCES public.evidence_sets(id) ON DELETE CASCADE;


--
-- Name: evidence_items evidence_items_normalized_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_normalized_entity_id_fkey FOREIGN KEY (normalized_entity_id) REFERENCES public.normalized_entities(id) ON DELETE CASCADE;


--
-- Name: evidence_sets evidence_sets_metric_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_sets
    ADD CONSTRAINT evidence_sets_metric_snapshot_id_fkey FOREIGN KEY (metric_snapshot_id) REFERENCES public.metric_snapshots(id) ON DELETE CASCADE;


--
-- Name: evidence_sets evidence_sets_normalized_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_sets
    ADD CONSTRAINT evidence_sets_normalized_snapshot_id_fkey FOREIGN KEY (normalized_snapshot_id) REFERENCES public.normalized_snapshots(id) ON DELETE CASCADE;


--
-- Name: evidence_sets evidence_sets_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_sets
    ADD CONSTRAINT evidence_sets_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: feishu_field_mappings feishu_field_mappings_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_field_mappings
    ADD CONSTRAINT feishu_field_mappings_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.feishu_resources(id) ON DELETE CASCADE;


--
-- Name: feishu_message_deliveries feishu_message_deliveries_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_message_deliveries
    ADD CONSTRAINT feishu_message_deliveries_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: feishu_resources feishu_resources_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feishu_resources
    ADD CONSTRAINT feishu_resources_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: human_approvals human_approvals_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_approvals
    ADD CONSTRAINT human_approvals_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: llm_executions llm_executions_node_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_executions
    ADD CONSTRAINT llm_executions_node_execution_id_fkey FOREIGN KEY (node_execution_id) REFERENCES public.node_executions(id) ON DELETE CASCADE;


--
-- Name: llm_executions llm_executions_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_executions
    ADD CONSTRAINT llm_executions_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: metric_snapshots metric_snapshots_normalized_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_snapshots
    ADD CONSTRAINT metric_snapshots_normalized_snapshot_id_fkey FOREIGN KEY (normalized_snapshot_id) REFERENCES public.normalized_snapshots(id) ON DELETE CASCADE;


--
-- Name: metric_snapshots metric_snapshots_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_snapshots
    ADD CONSTRAINT metric_snapshots_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: node_executions node_executions_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.node_executions
    ADD CONSTRAINT node_executions_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: normalized_entities normalized_entities_normalized_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.normalized_entities
    ADD CONSTRAINT normalized_entities_normalized_snapshot_id_fkey FOREIGN KEY (normalized_snapshot_id) REFERENCES public.normalized_snapshots(id) ON DELETE CASCADE;


--
-- Name: normalized_entities normalized_entities_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.normalized_entities
    ADD CONSTRAINT normalized_entities_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: normalized_snapshots normalized_snapshots_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.normalized_snapshots
    ADD CONSTRAINT normalized_snapshots_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: onboarding_sessions onboarding_sessions_credential_ref_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_sessions
    ADD CONSTRAINT onboarding_sessions_credential_ref_fkey FOREIGN KEY (credential_ref) REFERENCES public.encrypted_credentials(id);


--
-- Name: project_repositories project_repositories_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_repositories
    ADD CONSTRAINT project_repositories_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: publish_plans publish_plans_report_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publish_plans
    ADD CONSTRAINT publish_plans_report_version_id_fkey FOREIGN KEY (report_version_id) REFERENCES public.report_versions(id) ON DELETE CASCADE;


--
-- Name: publish_plans publish_plans_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publish_plans
    ADD CONSTRAINT publish_plans_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: report_artifacts report_artifacts_operation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_operation_id_fkey FOREIGN KEY (operation_id) REFERENCES public.side_effect_operations(id) ON DELETE CASCADE;


--
-- Name: report_artifacts report_artifacts_report_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_report_version_id_fkey FOREIGN KEY (report_version_id) REFERENCES public.report_versions(id) ON DELETE CASCADE;


--
-- Name: report_artifacts report_artifacts_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_artifacts
    ADD CONSTRAINT report_artifacts_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: report_claims report_claims_report_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_claims
    ADD CONSTRAINT report_claims_report_version_id_fkey FOREIGN KEY (report_version_id) REFERENCES public.report_versions(id) ON DELETE CASCADE;


--
-- Name: report_evidence report_evidence_claim_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_evidence
    ADD CONSTRAINT report_evidence_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.report_claims(id) ON DELETE CASCADE;


--
-- Name: report_evidence report_evidence_evidence_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_evidence
    ADD CONSTRAINT report_evidence_evidence_item_id_fkey FOREIGN KEY (evidence_item_id) REFERENCES public.evidence_items(id) ON DELETE CASCADE;


--
-- Name: report_runs report_runs_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_runs
    ADD CONSTRAINT report_runs_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: report_versions report_versions_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_versions
    ADD CONSTRAINT report_versions_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: run_status_history run_status_history_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_status_history
    ADD CONSTRAINT run_status_history_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id);


--
-- Name: side_effect_attempts side_effect_attempts_operation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effect_attempts
    ADD CONSTRAINT side_effect_attempts_operation_id_fkey FOREIGN KEY (operation_id) REFERENCES public.side_effect_operations(id) ON DELETE CASCADE;


--
-- Name: side_effect_operations side_effect_operations_publish_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effect_operations
    ADD CONSTRAINT side_effect_operations_publish_plan_id_fkey FOREIGN KEY (publish_plan_id) REFERENCES public.publish_plans(id) ON DELETE CASCADE;


--
-- Name: side_effect_operations side_effect_operations_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effect_operations
    ADD CONSTRAINT side_effect_operations_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: source_data_batches source_data_batches_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_data_batches
    ADD CONSTRAINT source_data_batches_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: tool_executions tool_executions_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tool_executions
    ADD CONSTRAINT tool_executions_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- Name: validation_results validation_results_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.validation_results
    ADD CONSTRAINT validation_results_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.report_runs(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

