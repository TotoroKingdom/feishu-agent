import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCredentialDraftSummary,
  clearCredentialDraft,
} from "../lib/configuration.js";

test("buildCredentialDraftSummary redacts the secret and derives a fingerprint suffix", async () => {
  const summary = await buildCredentialDraftSummary({
    credentialType: "github_pat",
    label: "primary",
    secret: "ghp_example_secret_value",
    status: "draft",
  });

  assert.equal(summary.credentialType, "github_pat");
  assert.equal(summary.maskedSecret, "••••••••••••••••••••••••");
  assert.equal(summary.secretEcho, "");
  assert.match(summary.fingerprintSuffix, /^[0-9a-f]{4}$/);
});

test("clearCredentialDraft removes any staged secret before reuse", () => {
  const cleared = clearCredentialDraft({
    credentialType: "github_pat",
    label: "primary",
    secret: "ghp_example_secret_value",
    status: "draft",
  });

  assert.equal(cleared.secret, "");
  assert.equal(cleared.fingerprintSuffix, "");
  assert.equal(cleared.status, "draft");
});
