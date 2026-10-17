"""Acceptance tests for evidence-backed scoring and generated-document drift."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_progress", ROOT / "scripts" / "update_progress.py")
assert SPEC is not None and SPEC.loader is not None
progress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(progress)


def example() -> dict:
    return {
        "schema_version": 1,
        "project": "Example",
        "release": "1.0",
        "updated": "2026-10-17",
        "scope": "Defined v1",
        "milestones": [
            {
                "id": "build", "title": "Build", "weight": 80,
                "items": [
                    {"id": "recipe", "title": "Recipe", "weight": 10,
                     "status": "complete", "evidence": ["tests/test_recipe.py: PASS"]},
                    {"id": "execution", "title": "Real execution", "weight": 70,
                     "status": "in_progress", "evidence": []},
                ],
            },
            {
                "id": "runtime", "title": "Runtime", "weight": 20,
                "items": [
                    {"id": "launch", "title": "Launch", "weight": 20,
                     "status": "pending", "evidence": []},
                ],
            },
        ],
    }


class ProgressScoringTests(unittest.TestCase):
    def test_weighted_criteria_not_task_count_or_work_in_progress(self):
        data = example()
        self.assertEqual(progress.total_progress(data), 10)
        generated = progress.render_progress(data, details=True)
        self.assertIn("10% — 10 / 100 points", generated)
        self.assertIn("12.5%", generated)
        self.assertIn("tests/test_recipe.py: PASS", generated)
        self.assertIn("[ ] **Real execution", generated)

    def test_complete_requires_evidence(self):
        data = example()
        data["milestones"][0]["items"][1]["status"] = "complete"
        with self.assertRaisesRegex(progress.ProgressError, "requires evidence"):
            progress.total_progress(data)
        data["milestones"][0]["items"][1]["evidence"] = ["CI #42: real build PASS"]
        self.assertEqual(progress.total_progress(data), 80)

    def test_regression_removes_points_without_reweighting(self):
        data = example()
        data["milestones"][0]["items"][0]["status"] = "in_progress"
        self.assertEqual(progress.total_progress(data), 0)
        self.assertEqual(data["milestones"][0]["weight"], 80)

    def test_unbalanced_or_noninteger_weights_are_rejected(self):
        mutations = [
            lambda data: data["milestones"][0].update(weight=81),
            lambda data: data["milestones"][0]["items"][0].update(weight=11),
            lambda data: data["milestones"][0]["items"][0].update(weight=True),
            lambda data: data["milestones"][0]["items"][0].update(weight=10.0),
        ]
        for mutate in mutations:
            data = example()
            mutate(data)
            with self.subTest(data=data), self.assertRaises(progress.ProgressError):
                progress.validate_progress(data)

    def test_duplicate_criteria_cannot_inflate_completion(self):
        data = example()
        data["milestones"][0]["items"][1]["id"] = "recipe"
        with self.assertRaisesRegex(progress.ProgressError, "duplicate"):
            progress.validate_progress(data)

    def test_scope_cannot_silently_drop_a_whole_milestone(self):
        data = example()
        data["milestones"].pop()
        with self.assertRaisesRegex(progress.ProgressError, "must total 100"):
            progress.validate_progress(data)

    def test_rejects_malformed_status_date_and_evidence(self):
        mutations = [
            lambda data: data.update(schema_version=True),
            lambda data: data.update(updated="2026-02-30"),
            lambda data: data["milestones"][0]["items"][0].update(status="almost"),
            lambda data: data["milestones"][0]["items"][0].update(evidence=[" "]),
            lambda data: data["milestones"][0]["items"][0].update(evidence=[progress.END]),
        ]
        for mutate in mutations:
            data = example()
            mutate(data)
            with self.subTest(data=data), self.assertRaises(progress.ProgressError):
                progress.validate_progress(data)


class ProgressDocumentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="maxkompilator-progress-")
        self.root = Path(self.directory.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "progress.json").write_text(json.dumps(example()), encoding="utf-8")
        for filename in progress.DOCUMENTS:
            (self.root / filename).write_text(
                "# Header\n\n" + progress.START + "\nStale\n" + progress.END + "\n\nKeep this footer.\n",
                encoding="utf-8",
            )

    def tearDown(self):
        self.directory.cleanup()

    def test_check_detects_drift_without_writing_and_sync_is_idempotent(self):
        path = self.root / "README.md"
        original = path.read_bytes()
        self.assertEqual(progress.sync_progress(self.root, check=True), ["README.md", "ROADMAP.md"])
        self.assertEqual(path.read_bytes(), original)
        progress.sync_progress(self.root)
        self.assertEqual(progress.sync_progress(self.root, check=True), [])
        self.assertEqual(progress.sync_progress(self.root), [])
        rendered = path.read_text(encoding="utf-8")
        self.assertTrue(rendered.startswith("# Header\n\n"))
        self.assertTrue(rendered.endswith("Keep this footer.\n"))

    def test_invalid_marker_in_second_document_prevents_partial_write(self):
        readme = self.root / "README.md"
        original = readme.read_bytes()
        (self.root / "ROADMAP.md").write_text("No markers here.\n", encoding="utf-8")
        with self.assertRaises(progress.ProgressError):
            progress.sync_progress(self.root)
        self.assertEqual(readme.read_bytes(), original)

    def test_duplicate_and_reversed_markers_are_rejected(self):
        for content in (
            progress.START + progress.START + progress.END,
            progress.END + progress.START,
        ):
            with self.subTest(content=content), self.assertRaises(progress.ProgressError):
                progress.replace_block(content, "new", "README.md")

    def test_command_line_exit_codes_support_ci(self):
        command = [sys.executable, str(ROOT / "scripts" / "update_progress.py"),
                   "--root", str(self.root), "--check"]
        before = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(before.returncode, 1, before.stderr)
        progress.sync_progress(self.root)
        after = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(after.returncode, 0, after.stderr)
        data = copy.deepcopy(example())
        data["milestones"][0]["items"][0]["evidence"] = []
        (self.root / "docs" / "progress.json").write_text(json.dumps(data), encoding="utf-8")
        invalid = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(invalid.returncode, 2, invalid.stderr)

    def test_repository_source_has_valid_fixed_scope(self):
        data = progress.load_progress(ROOT / "docs" / "progress.json")
        self.assertEqual(sum(m["weight"] for m in data["milestones"]), 100)
        self.assertLessEqual(progress.total_progress(data), 100)


if __name__ == "__main__":
    unittest.main()
