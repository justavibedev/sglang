# Hunyuan tool-schema type arrays: a reproducible parser failure

A legal tool parameter such as `{"type": ["integer", "null"]}` causes the baseline Hunyuan detector to call its scalar type normalizer with a list. Dictionary lookup then raises `TypeError: unhashable type: 'list'`. In non-streaming mode the exception handler returns no calls. In streaming mode it prevents the argument deltas from completing.

[Upstream draft PR #38940](https://github.com/sgl-project/sglang/pull/38940) expands scalar/list type declarations into individual normalized types, preserving the detector's existing type priority and null policy. The experiment uses the actual parser implementation, not a replacement parser.

## Pinned comparison

- Baseline: [`a26273d668c82400e9e2a97ed328d4148a04e123`](https://github.com/sgl-project/sglang/commit/a26273d668c82400e9e2a97ed328d4148a04e123)
- Fix: [`a20c6f8eaaedff111750ed1b12993dbd6a2a40b5`](https://github.com/justavibedev/sglang/commit/a20c6f8eaaedff111750ed1b12993dbd6a2a40b5)
- Python 3.12.11; macOS ARM64; all installed package versions in [requirements-lock.txt](requirements-lock.txt).
- The same regression test file from the fixed commit is overlaid onto both archived source trees.

| Measurement | Baseline | Fixed |
|---|---:|---:|
| New regression leaf checks passing | 0 / 183 | 183 / 183 |
| Regression unittest methods | 2 failing | 2 passing |
| Existing + new direct detector methods | Existing 41 passed before modification | 43 passing |

The 180 mode checks comprise 10 type/value pairs × 3 property-schema layouts × 3 chunk schedules × 2 modes. These are **30 distinct schema/value fixtures**, with 90 streaming schedules; the non-streaming assertion is repeated across those schedules. Three additional checks cover alias normalization and mixed scalar/list options. This is deterministic regression coverage, not a statistical sample or a model capability score.

Coverage includes nullable integers/numbers/booleans/strings/arrays/objects, an integer-or-null null value, mixed string/integer and string/array types, reversed type order, arrays inside `anyOf` and `oneOf` options, and two repeated tool calls to exercise streaming state reset. Values and their Python types must match expected values after JSON decoding. Chunk sizes are one character, seven characters, and a complete response.

## Reproduce

```bash
git clone --branch experiments/hunyuan-schema-type-arrays https://github.com/justavibedev/sglang.git
cd sglang
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r experiments/hunyuan-schema-type-arrays/requirements-lock.txt
.venv/bin/python experiments/hunyuan-schema-type-arrays/replay.py --output /tmp/hunyuan-parser-results
```

`replay.py` archives each exact commit into a temporary directory, overlays the identical tests, and invokes `run_source_tests.py`. A baseline subprocess exit of 1 is expected. The replay command succeeds only when the baseline has zero passing new checks and the fixed source has all 183 passing checks with a successful direct-detector test run.

Inspect [results/summary.json](results/summary.json), the per-case [baseline JSONL](results/baseline.jsonl) and [fixed JSONL](results/fixed.jsonl), and the complete compressed [baseline log](results/baseline.log.gz) and [fixed log](results/fixed.log.gz). Decompress logs with `gzip -dc`. Baseline logs intentionally retain the repeated caught exceptions from single-character streaming.

## Limits

The CPU harness bypasses SGLang package startup using package namespaces pointing at the archived source. It imports the real protocol, detector, base class, environment module, and JSON utilities unchanged. Only `sglang.test.test_utils.CustomTestCase` is replaced with `unittest.TestCase`, skipping GPU-idle checks and CI retry wrappers. The four `FunctionCallParser` integration methods are excluded. Normal upstream regression tests retain standard imports and the normal lifecycle.

No server, GPU, tokenizer/model generation, throughput, or task-success evaluation was performed. This experiment does not establish the frequency of these schemas in real traffic, and it does not change the existing interpretation of the literal `null` for nullable-string schemas. Upstream CI and maintainer review remain pending. Preparation used Codex assistance; this is an engineering experiment, not a peer-reviewed publication.

## Proposed next improvement

A shared contract test comparing streamed argument accumulation with non-streaming output across schema unions and chunk boundaries could prevent this class of defect across detectors. Maintainer agreement is **not yet established**. The first step is to obtain feedback on the narrow PR and ask whether shared contract coverage fits their test architecture before opening a larger implementation. Follow-up work should include full `FunctionCallParser` integration in the supported CI environment and maintainer-selected real-model serving fixtures.
