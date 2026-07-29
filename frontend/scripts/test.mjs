import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const target = process.argv[2] ?? "run-detail";
if (target !== "run-detail") {
  console.error(`Unknown frontend test target: ${target}`);
  process.exit(1);
}

const testFile = fileURLToPath(new URL("../tests/run-detail.test.mjs", import.meta.url));
const result = spawnSync(process.execPath, ["--test", testFile], {
  stdio: "inherit",
});

process.exit(result.status ?? 1);

