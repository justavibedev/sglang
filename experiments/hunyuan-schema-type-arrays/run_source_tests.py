"""CPU source harness; skips package startup and GPU-oriented test lifecycle only.

Real protocol, parser, environment, and JSON modules are imported unchanged.
The test_utils.CustomTestCase alias uses unittest.TestCase: no GPU idle check
or CI retry wrapper. This is source-level testing, not full server integration.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

parser = argparse.ArgumentParser()
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--all-detector-tests", action="store_true")
parser.add_argument("--jsonl", type=Path)
args = parser.parse_args()
root = args.repo.resolve()
for name in (
    "sglang",
    "sglang.srt",
    "sglang.srt.entrypoints",
    "sglang.srt.entrypoints.openai",
    "sglang.srt.function_call",
    "sglang.test",
    "sglang.test.ci",
):
    module = types.ModuleType(name)
    module.__path__ = [str(root / "python" / name.replace(".", "/"))]
    sys.modules[name] = module
lifecycle = types.ModuleType("sglang.test.test_utils")
lifecycle.CustomTestCase = unittest.TestCase
sys.modules[lifecycle.__name__] = lifecycle
path = root / "test/registered/unit/function_call/test_hunyuan_detector.py"
spec = importlib.util.spec_from_file_location("test_hunyuan_detector", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if args.all_detector_tests:
    suite = unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(value)
        for name, value in vars(module).items()
        if name.startswith("Test")
        and isinstance(value, type)
        and name != "TestHunyuanDetectorFunctionCallParser"
    )
else:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        module.TestHunyuanDetectorTypeArrays
    )


class RecordedResult(unittest.TextTestResult):
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        # Only leaf mode cases plus the normalization cases (not outer contexts).
        params = dict(subtest.params)
        if args.jsonl and ("mode" in params or "chunk_size" not in params):
            with args.jsonl.open("a") as output:
                output.write(
                    json.dumps(
                        {
                            "test": test.id(),
                            "parameters": params,
                            "passed": err is None,
                            "error": None if err is None else str(err[1]),
                        }
                    )
                    + "\n"
                )


if args.jsonl:
    args.jsonl.write_text("")
result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
sys.exit(not result.wasSuccessful())
