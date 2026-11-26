# V100 inference benchmarks

Local measurements of Lapilli, sFNX and Strata on two NVIDIA V100 32 GB GPUs, including MTP and DFlash2 configurations. This repository maintains reports, curated aggregate results and artifact provenance across engines.

## November 2026 comparison

- [Reviewed report](docs/reports/2026-11-26-v100-comparison.md)
- [Methodology and reproduction limits](docs/methodology.md)
- [Machine-readable results](results/2026-11-26/summary.json)
- [Parameter references](configs/2026-11-25/parameters.json)
- [Short summary for Lapilli upstream](docs/upstream/lapilli/v100-comparison.md)

The closest model-payload match used the Q4_K_XL Flash-Next backbone family and the same Q8 n-gram payload. It scored Strata 864, Lapilli 860 and sFNX 858 passes out of 966 graded trials. These are observations from one sampled suite. Engine packing, templates, arithmetic, drafter, cache policies and storage placement differed.

Lapilli led measured solo edit/code decode and the tested two-client end-to-end aggregate. sFNX led fresh synthetic prefill and solo prose decode. The report defines these metrics and their limits; neither the scores nor the replay investigation isolates speculation as the cause of a quality or formatting difference.

## What is published

The JSON results are extracted through explicit field allowlists. They contain aggregate counts, timings and source-artifact hashes. Parameter references preserve selected tested settings and original config digests; they are not runnable replacements for the original engine configs.

The private task fixtures, raw prompts, wire traces, model weights and engine binaries are not included. The original quality suite cannot currently be reproduced in full from this repository. A sanitized replacement suite must have a new hash and new measured scores.

## Check the published snapshot

Python 3.10 or newer, with no third-party packages:

```bash
python3 scripts/validate.py
```

To regenerate the curated snapshot from an existing local evidence archive:

```bash
python3 scripts/import_local_summary.py --evidence-root /path/to/v100-evaluation
python3 scripts/validate.py --write-manifest
python3 scripts/validate.py
```

The importer never copies raw fixtures, responses or transcripts. Review every proposed change before publishing it.

## Run the shareable prefill probe

Use an already-loaded, idle, OpenAI-compatible endpoint. This script does not stop services, switch models, execute tools or change engine settings.

```bash
python3 scripts/benchmark_prefill.py \
  --base-url http://127.0.0.1:18091/v1 \
  --model your-served-model \
  --output /path/outside-this-repo/prefill.jsonl
```

The probe collects client TTFT, wall time, usage and streamed decode rate. Engine timing fields are retained only when the response supplies them; client TTFT is not silently relabeled as engine prefill time. Set `BENCHMARK_API_KEY` in the environment if authentication is required. Results contain no authentication headers or response text. See [methodology](docs/methodology.md) before comparing runs.

## Stable citations and upstream docs

Use the dated [`v2026.11.26` snapshot](https://github.com/nkhaooat/v100-inference-benchmarks/tree/v2026.11.26) for citations to these results. A short Lapilli-specific summary is prepared under `docs/upstream/lapilli/`; the full report lives here so upstream documentation can link to one maintained source.

Published material in this repository is MIT licensed. Model weights, engines and external datasets retain their own licenses and are not redistributed here.
