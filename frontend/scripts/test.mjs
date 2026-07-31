import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const targets = process.argv.slice(2);
const targetFiles = {
  dashboard: "../tests/dashboard.test.mjs",
  runs: "../tests/runs.test.mjs",
  "run-detail": "../tests/run-detail.test.mjs",
  "repository-config": "../tests/repository-config.test.mjs",
  "feishu-resource-mapping": "../tests/feishu-resource-mapping.test.mjs",
  credentials: "../tests/credentials.test.mjs",
  "config-confirmation": "../tests/config-confirmation.test.mjs",
  auth: "../tests/auth.test.mjs",
};

const selectedTargets = targets.length > 0 ? targets : ["run-detail"];

for (const target of selectedTargets) {
  const relativeTestFile = targetFiles[target];
  if (!relativeTestFile) {
    console.error(`Unknown frontend test target: ${target}`);
    process.exit(1);
  }

  const testFile = fileURLToPath(new URL(relativeTestFile, import.meta.url));
  const result = spawnSync(process.execPath, ["--test", testFile], {
    stdio: "inherit",
  });

  if ((result.status ?? 1) !== 0) {
    process.exit(result.status ?? 1);
  }
}
