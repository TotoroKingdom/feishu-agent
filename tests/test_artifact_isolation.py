from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import _ops, dependency_scan, full_ci_local, sbom, secret_scan
from scripts import recovery_drill as recovery_drill_module


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RUN_ID = "20260804T120000+0800-r1-test"


class GeneratedArtifactIsolationTest(unittest.TestCase):
    def test_sbom_uses_an_isolated_generated_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            artifacts = Path(temporary_directory) / "artifacts"
            with (
                patch.object(sbom, "ARTIFACTS", artifacts),
                patch.object(_ops, "ARTIFACT_RUN_ID", RUN_ID, create=True),
                patch.object(sbom, "run") as run,
            ):
                sbom.main()

            output_paths = []
            for call in run.call_args_list:
                command = call.args[0]
                if "--output" in command:
                    output_paths.append(Path(command[command.index("--output") + 1]))

            expected_directory = artifacts / "generated" / RUN_ID / "sbom"
            self.assertEqual(len(output_paths), 3)
            self.assertTrue(
                all(path.parent == expected_directory for path in output_paths)
            )

    def test_recovery_drill_uses_an_isolated_generated_run_directory(self) -> None:
        try:
            with patch.object(_ops, "ARTIFACT_RUN_ID", RUN_ID, create=True):
                recovery_drill = importlib.reload(recovery_drill_module)

                expected_directory = (
                    recovery_drill.ARTIFACTS / "generated" / RUN_ID / "recovery-drill"
                )
                self.assertEqual(recovery_drill.BACKUP_PATH.parent, expected_directory)
                self.assertEqual(recovery_drill.SEED_PATH.parent, expected_directory)
        finally:
            importlib.reload(recovery_drill_module)

    def test_each_ci_or_scan_snapshot_uses_an_isolated_run_directory(self) -> None:
        cases = (
            (full_ci_local, "full-ci", "alembic.sql"),
            (dependency_scan, "dependency-scan", "backend.pip-check.txt"),
            (secret_scan, "secret-scan", "compose.config.yml"),
        )

        for module, category, expected_name in cases:
            with self.subTest(category=category):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    artifacts = Path(temporary_directory) / "artifacts"
                    context_managers = [
                        patch.object(module, "ARTIFACTS", artifacts),
                        patch.object(_ops, "ARTIFACT_RUN_ID", RUN_ID, create=True),
                        patch.object(module, "run"),
                    ]
                    if module is secret_scan:
                        context_managers.append(
                            patch.object(
                                secret_scan, "_iter_text_files", return_value=[]
                            )
                        )

                    with (
                        context_managers[0],
                        context_managers[1],
                        context_managers[2] as run,
                    ):
                        if len(context_managers) == 4:
                            with context_managers[3]:
                                module.main()
                        else:
                            module.main()

                    output_paths = [
                        Path(call.kwargs["stdout"].name)
                        for call in run.call_args_list
                        if call.kwargs.get("stdout") is not None
                    ]
                    expected_path = (
                        artifacts / "generated" / RUN_ID / category / expected_name
                    )
                    self.assertIn(expected_path, output_paths)

                    if module is full_ci_local:
                        propagated_environments = [
                            call.kwargs.get("env")
                            for call in run.call_args_list
                            if any(
                                script_name in " ".join(call.args[0])
                                for script_name in (
                                    "dependency_scan.py",
                                    "secret_scan.py",
                                )
                            )
                        ]
                        self.assertEqual(
                            propagated_environments,
                            [
                                {_ops.ARTIFACT_RUN_ID_ENV: RUN_ID},
                                {_ops.ARTIFACT_RUN_ID_ENV: RUN_ID},
                            ],
                        )


class PackagingMetadataIsolationTest(unittest.TestCase):
    def test_setuptools_metadata_does_not_write_egg_info_beside_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            source = temporary_root / "backend"
            source.mkdir()
            (source / "app").mkdir()
            (source / ".build-metadata").mkdir()
            shutil.copy2(BACKEND / "pyproject.toml", source / "pyproject.toml")
            shutil.copy2(
                BACKEND / "app" / "__init__.py", source / "app" / "__init__.py"
            )
            setup_config = BACKEND / "setup.cfg"
            if setup_config.exists():
                shutil.copy2(setup_config, source / "setup.cfg")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from setuptools import setup; setup()",
                    "egg_info",
                ],
                cwd=source,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(list(source.glob("*.egg-info")), [])
            self.assertEqual(
                len(list((source / ".build-metadata").glob("*.egg-info"))), 1
            )


class PipelineArtifactContractTest(unittest.TestCase):
    def test_sbom_upload_reads_the_generated_run_directory(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "FEISHU_AGENT_ARTIFACT_RUN_ID: github-${{ github.run_id }}-${{ github.run_attempt }}",
            workflow,
        )
        self.assertIn(
            "path: artifacts/generated/${{ env.FEISHU_AGENT_ARTIFACT_RUN_ID }}/sbom",
            workflow,
        )
        self.assertIn("if-no-files-found: error", workflow)
        self.assertNotIn("path: artifacts/sbom", workflow)

    def test_typescript_incremental_cache_is_written_below_ignored_next(self) -> None:
        config = json.loads((ROOT / "frontend" / "tsconfig.json").read_text("utf-8"))

        self.assertEqual(
            config["compilerOptions"].get("tsBuildInfoFile"),
            ".next/cache/tsconfig.tsbuildinfo",
        )


class ArtifactRunIdSafetyTest(unittest.TestCase):
    def test_windows_reserved_or_ambiguous_run_ids_are_rejected(self) -> None:
        for run_id in ("CON", "CON.txt", "nul", "COM1", "LPT9", "run."):
            with self.subTest(run_id=run_id):
                with patch.dict(
                    os.environ, {_ops.ARTIFACT_RUN_ID_ENV: run_id}, clear=False
                ):
                    with self.assertRaises(ValueError):
                        _ops._resolve_artifact_run_id()


if __name__ == "__main__":
    unittest.main()
