from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import demo


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run-demo.sh"
SCENARIO = HERE / "04-report-export-isolation.md"
ROUTING = HERE / "senior-scenarios-README.md"


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.offset = 0
        self.closed = False

    def execute(self, statement):
        self.offset = 0

    def fetchall(self):
        return list(self.rows)

    def fetchmany(self, size):
        batch = self.rows[self.offset : self.offset + size]
        self.offset += len(batch)
        return batch

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.cursors = []

    def cursor(self):
        cursor = FakeCursor(self.rows)
        self.cursors.append(cursor)
        return cursor


class FakeOltpWorker:
    def __init__(self, connection_factory):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class DemoUnitTests(unittest.TestCase):
    def test_canonical_row_is_stable_and_rejects_tsv_breakers(self):
        self.assertEqual(
            b"7\tpaid\t12.30\n",
            demo.canonical_row((7, "paid", Decimal("12.30"))),
        )
        with self.assertRaises(ValueError):
            demo.canonical_row((7, "bad\tvalue"))
        with self.assertRaises(ValueError):
            demo.canonical_row((7, "bad\nvalue"))

    def test_buffered_and_chunked_exports_have_identical_count_order_and_sha(self):
        rows = [(1, 10, "paid"), (2, 20, "shipped"), (3, 30, "paid")]
        buffered_connection = FakeConnection(rows)
        chunked_connection = FakeConnection(rows)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            buffered = demo.export_buffered(
                buffered_connection, root / "buffered.tsv"
            )
            chunked = demo.export_chunked(
                chunked_connection, root / "chunked.tsv", batch_size=2
            )
            self.assertEqual(
                (root / "buffered.tsv").read_bytes(),
                (root / "chunked.tsv").read_bytes(),
            )
        self.assertEqual(3, buffered["rows"])
        self.assertEqual(buffered["rows"], chunked["rows"])
        self.assertEqual([1, 10], buffered["first_key"])
        self.assertEqual(buffered["first_key"], chunked["first_key"])
        self.assertEqual([3, 30], buffered["last_key"])
        self.assertEqual(buffered["last_key"], chunked["last_key"])
        self.assertEqual(buffered["sha256"], chunked["sha256"])
        self.assertTrue(buffered_connection.cursors[0].closed)
        self.assertTrue(chunked_connection.cursors[0].closed)

    def test_run_demo_requires_equal_exports_and_oltp_progress(self):
        export = {
            "rows": 30000,
            "first_key": [1, 1],
            "last_key": [10000, 30000],
            "sha256": "a" * 64,
            "elapsed_seconds": 0.25,
        }
        totals = iter((10, 12, 20, 23))
        worker = FakeOltpWorker(None)
        with tempfile.TemporaryDirectory() as directory, mock.patch.multiple(
            demo,
            prepare_database=mock.DEFAULT,
            export_buffered=mock.DEFAULT,
            export_chunked=mock.DEFAULT,
            probe_total=mock.DEFAULT,
            OltpWorker=mock.DEFAULT,
        ) as patched:
            patched["prepare_database"].return_value = None
            patched["export_buffered"].return_value = dict(export)
            patched["export_chunked"].return_value = dict(export)
            patched["probe_total"].side_effect = lambda factory: next(totals)
            patched["OltpWorker"].return_value = worker
            summary = demo.run_demo(lambda **kwargs: None, Path(directory))
        self.assertTrue(worker.started)
        self.assertTrue(worker.stopped)
        self.assertEqual("SCALED_REPRODUCED", summary["status"])
        self.assertEqual(
            {"rows": True, "order": True, "sha256": True},
            summary["equality"],
        )
        self.assertEqual(2, summary["oltp"]["buffered_delta"])
        self.assertEqual(3, summary["oltp"]["chunked_delta"])


class ShellPolicyTests(unittest.TestCase):
    def test_run_uses_only_scoped_bounded_docker_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            calls = root / "calls.log"
            fake_docker = fake_bin / "docker"
            fake_docker.write_text(
                """#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$FAKE_DOCKER_CALLS"
case "${1-} ${2-}" in
  "container inspect"|"network inspect"|"volume inspect") exit 1 ;;
esac
if test "${1-}" = inspect; then
  case "$*" in
    *State.Health.Status*) printf '%s\\n' healthy ;;
    *) printf '%s\\n' mysql-senior-demo ;;
  esac
fi
exit 0
""",
                encoding="utf-8",
            )
            fake_docker.chmod(0o755)
            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "FAKE_DOCKER_CALLS": str(calls),
                    "DEMO_NO_WAIT": "1",
                }
            )
            result = subprocess.run(
                [str(RUNNER), "run"],
                cwd=HERE,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            observed = calls.read_text(encoding="utf-8")
            self.assertIn("--label com.openai.codex.scope=mysql-senior-demo", observed)
            self.assertIn("--cpus 2 --memory 2g --pids-limit 256", observed)
            self.assertIn("mysql-senior-demo-mysql", observed)
            self.assertIn("mysql-senior-demo-runner", observed)
            self.assertIn("mysql-senior-demo-net", observed)
            self.assertIn("mysql-senior-demo-data", observed)
            self.assertNotIn("type=bind", observed)
            self.assertNotIn("/private/tmp", observed)
            self.assertNotIn("mysql-primary", observed)
            self.assertNotIn("mysql-senior-scenarios-", observed)


class DocumentationContractTests(unittest.TestCase):
    def test_chapter_follows_the_engineering_decision_order(self):
        text = SCENARIO.read_text(encoding="utf-8")
        headings = (
            "## 1. 先定义问题",
            "## 2. 数据与索引",
            "## 3. 一致性边界",
            "## 4. 执行策略",
            "## 5. 隔离 OLTP",
            "## 6. 如何观测",
            "## 7. Docker 缩小实验",
            "## 8. 失败与恢复",
        )
        positions = [text.index(heading) for heading in headings]
        self.assertEqual(sorted(positions), positions)

    def test_chapter_exposes_the_small_demo_and_exact_boundaries(self):
        text = SCENARIO.read_text(encoding="utf-8")
        for required in (
            "./run-demo.sh test",
            "./run-demo.sh run",
            "./run-demo.sh cleanup",
            "fetchall()",
            "fetchmany(1000)",
            "(created_at, id, item_id)",
            "MVCC",
            "undo",
            "OLTP counter",
            "10,000",
            "30,000",
            "不能外推",
        ):
            self.assertIn(required, text)
        for abandoned in (
            "Task 10",
            "seventh runtime",
            "eighth runtime",
            "one-shot",
            "calibration matrix",
            "manifest chain",
            "run-containerized.sh",
        ):
            self.assertNotIn(abandoned, text)

    def test_routing_uses_the_simple_lab_and_truthful_pre_run_status(self):
        text = ROUTING.read_text(encoding="utf-8")
        self.assertIn("[container lab](../00-lab/senior-scenarios/README.md)", text)
        self.assertIn("等待 Docker 缩小实验", text)
        self.assertIn("`READY_UNRUN`", text)
        self.assertNotIn("等待 Task 10", text)


if __name__ == "__main__":
    unittest.main()
