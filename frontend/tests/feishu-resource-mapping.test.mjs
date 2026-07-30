import assert from "node:assert/strict";
import test from "node:test";

import { summarizeFeishuMappingConfiguration } from "../lib/configuration.js";

const resource = {
  id: "res-1",
  project_id: "project-1",
  resource_type: "bitable",
  external_id: "tbl_123",
  name: "Weekly Tracker",
  schema_hash: "6f1b4b4f6f8a8d9f1e8b7c7a3c4d5e6f7a8b9c0d1e2f345678901234567890ab",
  enabled: true,
  revision: 2,
  last_connectivity_status: "ok",
  last_connectivity_at: "2026-07-30T01:00:00Z",
  updated_at: "2026-07-30T01:00:00Z",
};

test("summarizeFeishuMappingConfiguration marks missing critical logical fields", () => {
  const summary = summarizeFeishuMappingConfiguration(resource, {
    schemaHash: resource.schema_hash,
    fields: [
      { logicalField: "title", externalFieldId: "fld_title", requiredLevel: "required" },
      { logicalField: "owner", externalFieldId: "fld_owner", requiredLevel: "optional" },
    ],
    requiredLogicalFields: ["task_id", "title"],
  });

  assert.equal(summary.status, "missing_critical");
  assert.deepEqual(summary.missingCriticalFields, ["task_id"]);
  assert.equal(summary.schemaStatus, "matched");
  assert.equal(summary.fingerprintSuffix, "90ab");
});

test("summarizeFeishuMappingConfiguration detects schema hash conflicts", () => {
  const summary = summarizeFeishuMappingConfiguration(resource, {
    schemaHash: "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    fields: [
      { logicalField: "task_id", externalFieldId: "fld_task_id", requiredLevel: "critical" },
      { logicalField: "title", externalFieldId: "fld_title", requiredLevel: "required" },
    ],
    requiredLogicalFields: ["task_id", "title"],
  });

  assert.equal(summary.status, "schema_conflict");
  assert.equal(summary.schemaStatus, "conflict");
  assert.match(summary.schemaMessage, /冲突/);
});
