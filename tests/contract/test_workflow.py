"""Workflow orchestration must preserve failures and restrict every data push."""

import importlib.util
import io
import json
import os
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("collection_workflow", ROOT / ".github/scripts/collect.py")
WORKFLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKFLOW)


class WorkflowTests(unittest.TestCase):
    def environment(self, root):
        return {"RUNNER_TEMP": str(root), "GITHUB_OUTPUT": str(root / "outputs"), "GITHUB_STEP_SUMMARY": str(root / "summary"),
                "CVM_COLLECT_CATEGORY": "resolucoes", "CVM_COLLECT_BATCH": "3", "CVM_COLLECT_LIMIT": "10", "CVM_COLLECT_MODE": "batch"}

    def call(self, action):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return WORKFLOW.main([action])

    def test_cli_exit_two_and_three_cannot_be_masked_by_output_parsing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for code in (2, 3):
                with self.subTest(code=code), patch.dict(os.environ, self.environment(root), clear=True), \
                        patch.object(WORKFLOW, "git", return_value=SimpleNamespace(stdout="001-acervo-cvm\n")), \
                        patch.object(WORKFLOW.subprocess, "run", return_value=SimpleNamespace(returncode=code, stdout='{"changed": true}\n', stderr="blocked")):
                    self.assertEqual(self.call("run"), code)
                    self.assertFalse((root / "outputs").exists())
                    self.assertFalse(WORKFLOW.result_path().exists())

    def test_inputs_reach_cli_as_arguments_and_result_is_boolean(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = {**self.environment(root), "CVM_COLLECT_DOCUMENT": "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html"}
            with patch.dict(os.environ, environment, clear=True), patch.object(WORKFLOW, "guard_branch"), \
                    patch.object(WORKFLOW.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout='{"changed": false}\n', stderr="")) as process:
                self.assertEqual(self.call("run"), 0)
                args = process.call_args.args[0]
                self.assertEqual(args[args.index("--batch") + 1], "3")
                self.assertEqual(args[args.index("--limit") + 1], "10")
                self.assertEqual(args[args.index("--document") + 1], environment["CVM_COLLECT_DOCUMENT"])
                self.assertEqual(args[args.index("--min-interval") + 1], "5")
                self.assertEqual((root / "outputs").read_text(), "changed=false\n")

    def test_schedule_uses_incremental_and_zero_limit_remains_unlimited(self):
        with TemporaryDirectory() as temporary, patch.dict(os.environ, {**self.environment(Path(temporary)), "CVM_COLLECT_MODE": "incremental", "CVM_COLLECT_LIMIT": "0"}, clear=True):
            args, label = WORKFLOW.parameters()
            self.assertIn("--incremental", args)
            self.assertNotIn("--limit", args)
            self.assertEqual(label, "resolucoes incremental")

    def test_changed_string_or_missing_json_is_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for output in ('{"changed": "false"}', "", "not JSON"):
                with self.subTest(output=output), patch.dict(os.environ, self.environment(root), clear=True), \
                        patch.object(WORKFLOW, "guard_branch"), patch.object(WORKFLOW.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=output, stderr="")):
                    self.assertEqual(self.call("run"), 2)

    def test_main_and_detached_head_fail_before_collecting_or_committing(self):
        for branch in ("main", "t/other", ""):
            with self.subTest(branch=branch), patch.object(WORKFLOW, "git", return_value=SimpleNamespace(stdout=branch)) as git:
                self.assertEqual(self.call("run"), 2)
                self.assertEqual(self.call("commit"), 2)
                self.assertTrue(all(call.args == ("branch", "--show-current") for call in git.call_args_list))

    def test_no_change_or_empty_stage_never_commits(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(os.environ, self.environment(root), clear=True), patch.object(WORKFLOW, "guard_branch"), \
                    patch.object(WORKFLOW, "git", return_value=SimpleNamespace(stdout="")) as git:
                WORKFLOW.result_path().write_text(json.dumps({"summary": {"changed": False}}))
                self.assertEqual(self.call("commit"), 0)
                git.assert_not_called()

    def test_staged_code_is_rejected_without_a_commit_or_push(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(os.environ, self.environment(root), clear=True), patch.object(WORKFLOW, "guard_branch"), \
                    patch.object(WORKFLOW.Path, "is_dir", return_value=True), patch.object(WORKFLOW, "git", return_value=SimpleNamespace(stdout="src/cvm_archive/cli.py\n")) as git:
                WORKFLOW.result_path().write_text(json.dumps({"summary": {"changed": True}}))
                self.assertEqual(self.call("commit"), 2)
                self.assertFalse(any(call.args[0] in ("commit", "push") for call in git.call_args_list))

    def test_data_commit_uses_bot_exact_target_and_real_collection_label(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            def git(*args, **kwargs):
                return SimpleNamespace(stdout="cobertura/cobertura.json\n" if args[:3] == ("diff", "--cached", "--name-only") else "")
            with patch.dict(os.environ, self.environment(root), clear=True), patch.object(WORKFLOW, "guard_branch"), \
                    patch.object(WORKFLOW.Path, "is_dir", return_value=True), patch.object(WORKFLOW, "git", side_effect=git) as calls:
                WORKFLOW.result_path().write_text(json.dumps({"summary": {"changed": True}, "label": "resolucoes batch 3", "date": "2026-10-30"}))
                self.assertEqual(self.call("commit"), 0)
                commit = next(call for call in calls.call_args_list if call.args[0] == "commit")
                self.assertIn("batch 3", commit.args[2])
                self.assertIn("2026-10-30", commit.args[2])
                self.assertEqual(commit.kwargs["env"]["GIT_AUTHOR_NAME"], "github-actions[bot]")
                self.assertEqual(commit.kwargs["env"]["GIT_COMMITTER_EMAIL"], WORKFLOW.BOT["GIT_COMMITTER_EMAIL"])
                self.assertEqual(calls.call_args_list[-1].args, ("push", "origin", "HEAD:001-acervo-cvm"))

    def test_workflow_wiring_does_not_collect_on_push(self):
        source = (ROOT / ".github/workflows/collect.yml").read_text(encoding="utf-8")
        self.assertNotIn("  push:", source)
        self.assertNotIn("  pull_request:", source)
        self.assertIn("cancel-in-progress: false", source)
        self.assertIn("runs-on: ubuntu-24.04", source)
        self.assertIn("ref: 001-acervo-cvm", source)
        self.assertIn("CVM_COLLECT_LIMIT:", source)
        self.assertIn("python .github/scripts/collect.py run", source)
        self.assertIn("python .github/scripts/collect.py commit", source)


if __name__ == "__main__":
    unittest.main()
