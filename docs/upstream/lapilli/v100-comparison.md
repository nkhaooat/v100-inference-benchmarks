# V100 configuration comparison, November 2026

An independent local comparison evaluated Lapilli, sFNX and Strata on a Ryzen 9 7945HX3D with 96 GiB installed RAM and two V100 32 GB GPUs (one PCIe, one SXM2).

The closest model-payload match used the Q4_K_XL Flash-Next backbone family and an identical Q8 n-gram payload. Across 966 graded trials, Lapilli MTP8 passed 860, sFNX DFlash2 passed 858 and Strata DFlash2 Q4 passed 864. The small observed gaps come from one sampled suite; templates, packing, numerical execution, drafter and cache settings differed, so this does not isolate the quality effect of speculation.

In that comparison, Lapilli achieved approximately 146 tok/s on solo `edit1` decode and 118 tok/s on solo `code1`. Its tested concurrent `code1`/`prose2` pair achieved approximately 102 tok/s aggregate end-to-end throughput. Fresh synthetic prefill at approximately 35.8k Qwen tokens was approximately 1,453 tok/s for Lapilli, 2,060 for sFNX and 384 for Strata. Solo workloads ran twice; the concurrent pair ran once per arm.

The full report covers MTP4/MTP8 observations, DeepSeek configurations, cache behavior, parser failures and artifact pins. The original quality fixtures remain private; the repository publishes curated summaries and a shareable synthetic prefill probe, not a complete reproduction of the quality suite.

- [Full report and limitations — dated snapshot](https://github.com/nkhaooat/v100-inference-benchmarks/blob/v2026.11.26/docs/reports/2026-11-26-v100-comparison.md)
- [Curated machine-readable results](https://github.com/nkhaooat/v100-inference-benchmarks/blob/v2026.11.26/results/2026-11-26/summary.json)
- [Methodology and metric definitions](https://github.com/nkhaooat/v100-inference-benchmarks/blob/v2026.11.26/docs/methodology.md)

These are observations of the tested configurations, not a universal default-model recommendation. The original strict grades were retained after parser investigations; an incomplete live repeat contributes no additional score.
