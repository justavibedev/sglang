"""Replay both pinned commits with identical regression tests; no server/GPU."""

import argparse
import gzip
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile

BASELINE = "a26273d668c82400e9e2a97ed328d4148a04e123"
FIXED = "a20c6f8eaaedff111750ed1b12993dbd6a2a40b5"
TEST_PATH = "test/registered/unit/function_call/test_hunyuan_detector.py"
HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=HERE / "results")
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
repo = HERE.parents[1]
regression_tests = subprocess.check_output(
    ["git", "show", FIXED + ":" + TEST_PATH], cwd=repo
)
summary = {
    "baseline_commit": BASELINE,
    "fixed_commit": FIXED,
    "python": sys.version,
    "platform": platform.platform(),
    "runs": {},
}
for label, commit in [("baseline", BASELINE), ("fixed", FIXED)]:
    archive = subprocess.check_output(["git", "archive", commit], cwd=repo)
    with tempfile.TemporaryDirectory(prefix="sglang-parser-replay-") as directory:
        source = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(source, filter="data")
        (source / TEST_PATH).write_bytes(regression_tests)
        command = [
            sys.executable,
            str(HERE / "run_source_tests.py"),
            "--repo",
            str(source),
            "--jsonl",
            str(output / f"{label}.jsonl"),
        ]
        if label == "fixed":
            command.append("--all-detector-tests")
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        # Preserve the complete raw output; baseline repeats its caught exception
        # for every character chunk, so compress without discarding those messages.
        with gzip.GzipFile(
            filename=str(output / f"{label}.log.gz"), mode="wb", mtime=0
        ) as log:
            log.write(result.stdout)
        rows = [
            json.loads(row)
            for row in (output / f"{label}.jsonl").read_text().splitlines()
        ]
        regressions = [row for row in rows if "TypeArrays" in row["test"]]
        summary["runs"][label] = {
            "exit_code": result.returncode,
            "regression_leaf_checks": len(regressions),
            "regression_leaf_checks_passed": sum(row["passed"] for row in regressions),
        }
        print(label, summary["runs"][label])
(output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
assert summary["runs"]["baseline"]["exit_code"] == 1
assert summary["runs"]["baseline"]["regression_leaf_checks_passed"] == 0
assert summary["runs"]["fixed"]["exit_code"] == 0
assert summary["runs"]["fixed"]["regression_leaf_checks_passed"] == 183
