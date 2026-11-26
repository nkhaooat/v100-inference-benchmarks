#!/usr/bin/env python3
"""Extract explicitly selected aggregates; never copy requests or private fixtures."""

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load(root, relative):
    path = root / relative
    raw = path.read_bytes()
    return json.loads(raw), {"archive_record": relative, "sha256": hashlib.sha256(raw).hexdigest()}


def numeric_fields(value, names):
    return {name: value[name] for name in names
            if name in value and isinstance(value[name], (int, float)) and not isinstance(value[name], bool)}


def counts(arm):
    groups = {}
    for name in ("local", "humaneval", "long_context", "concurrency", "xml_tools", "tools_protocol"):
        if name not in arm["groups"]:
            continue
        group = arm["groups"][name]
        groups["tools_protocol" if name == "xml_tools" else name] = numeric_fields(
            group, ("passed", "graded", "executed", "capped", "capped_status_count"))
    return {"passed": arm["passed"], "graded": arm.get("graded", 966), "groups": groups}


def speed(value):
    """Only workload counters/timings, never payloads, chunks, answers or paths."""
    result = numeric_fields(value, ("two_client_aggregate_tokens_s",))
    for key in ("edit1", "code1", "prose2", "edit1-c1", "code1-c1", "code1-c2", "prose2-c1", "prose2-c2"):
        if key in value:
            result[key] = numeric_fields(value[key], (
                "runs", "mean_decode_tokens_s", "mean_elapsed_s", "stream_decode_tok_s_mean", "ttft_s_mean"))
    if isinstance(value.get("fresh_35k"), dict):
        result["fresh_35k"] = numeric_fields(value["fresh_35k"], (
            "mean_prompt_tokens", "mean_prefill_tokens_s", "mean_ttft_s"))
    if isinstance(value.get("fresh_prefill"), dict):
        result["fresh_prefill"] = {}
        for tier in ("128", "512", "2048"):
            if tier in value["fresh_prefill"]:
                result["fresh_prefill"][tier] = numeric_fields(value["fresh_prefill"][tier], (
                    "runs", "mean_prompt_tokens", "mean_prefill_tokens_s", "mean_prompt_tokens_s", "mean_ttft_s"))
    return result


def output(relative, value):
    path = REPO / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.evidence_root

    earlier, source_earlier = load(root, "2026-11-25-sfnx-mtp8-benchmark/final-comparison.json")
    deepseek, source_deepseek = load(root, "2026-11-25-lapilli-deepseek/final-comparison.json")
    q8, source_q8 = load(root, "2026-11-25-flash-next-q8-engram/final-comparison.json")
    pins, source_pins = load(root, "2026-11-25-flash-next-q8-engram/benchmark-pins.json")
    replay, source_replay = load(root, "2026-11-26-tool-protocol-investigation/sfnx-candidate-raw-replay.json")
    qualification, source_qualification = load(root, "2026-11-26-tool-protocol-investigation/sfnx-serving-fix-report.json")

    earlier_arms = []
    for arm_id, speed_id in (
        ("strata_saved", "strata_speed_refresh"), ("lapilli_mtp8", "lapilli_mtp8"),
        ("sfnx_dflash2", "sfnx_dflash2"), ("sfnx_mtp8", "sfnx_mtp8"), ("lapilli_mtp4", "lapilli_mtp4"),
    ):
        earlier_arms.append({"id": arm_id, **counts(earlier["quality"][arm_id]),
                             "speed": speed(earlier["speed"][speed_id])})
    q8_arms = []
    for arm_id in ("strata-dflash2-q4", "lapilli-mtp8", "sfnx-dflash2"):
        original = q8["arms"][arm_id]
        performance = speed(original["speed"])
        performance.update(speed(original))
        q8_arms.append({"id": arm_id, **counts(original), "speed": performance,
                        "pins": {key: pins["arms"][arm_id][key] for key in ("binary_sha256", "config_sha256")}})
    pairs = []
    for pair in q8["paired"].values():
        pairs.append({"left": pair["left"], "right": pair["right"],
                      **numeric_fields(pair["total"], ("both_passed", "both_failed", "left_only_passed", "right_only_passed"))})
    summary = {
        "schema_version": 1,
        "snapshot": "2026-11-26",
        "publication_scope": "Curated aggregate results; private fixtures and raw responses are not included. No new inference was run to generate this snapshot.",
        "hardware": {"cpu": "Ryzen 9 7945HX3D", "ram_installed_gib": 96,
                     "ram_linux_visible_gib_approx": 93.5,
                     "gpus": ["V100 PCIe 32 GB (stock PCIe VBIOS)",
                              "V100 32 GB PCIe card with cross-flashed SXM2 VBIOS"],
                     "gpu_link": "PCIe Gen3 x8 per card; peer-to-peer enabled, AMD IOMMU off, peer path verified per campaign"},
        "campaigns": [
            {"id": "flash-next-initial", "source": source_earlier,
             "scope": "Historical configurations; target quantization, dates and draft settings differ.", "arms": earlier_arms},
            {"id": "lapilli-deepseek", "source": source_deepseek,
             "scope": "Family-native sampling; Nace used a qualified router patch.",
             "arms": [{"id": arm_id, **counts(deepseek["quality"][arm_id]), "speed": speed(deepseek["speed"][arm_id])}
                      for arm_id in ("nace", "ista")]},
            {"id": "flash-next-q8-engram", "source": source_q8,
             "scope": "Shared Q4_K_XL backbone family and Q8 n-gram payload; not complete engine numerical parity.",
             "suite_sha256": pins["suite_sha256"], "q8_payload_sha256": pins["q8_payload_sha256"],
             "arms": q8_arms, "paired": pairs},
        ],
        "parser_replay": {"source": source_replay, "counts": numeric_fields(replay["counts"], (
            "trials", "responses", "responses_with_multiple_raw_records", "changed_responses",
            "changed_previously_passing_responses", "chunk_invariance_checks")),
            "native_qualification": {"source": source_qualification,
                                     **numeric_fields(qualification["native_api"], ("executed", "graded", "strict_passed"))},
            "scope": "Parser replay and targeted native qualification; original full-suite grades are unchanged."},
    }
    output("results/2026-11-26/summary.json", summary)

    parameters = {
        "schema_version": 1, "campaign": "flash-next-q8-engram", "source": source_pins,
        "scope": "Selected parameter references, not executable engine configs. Original config digests identify the private records, not this transformed file.",
        "max_context_tokens": 262144, "parallel_slots": 2,
        "sampling": {mode: numeric_fields(earlier["configuration"]["sampling"][mode], (
            "temperature", "top_p", "top_k", "min_p", "presence_penalty", "frequency_penalty", "repetition_penalty"))
                     for mode in ("nonthinking", "thinking")},
        "arms": [],
    }
    config_fields = ("mmap-experts", "resident-experts", "peer-exclusive", "ram-reserve-mib", "vram-reserve-mib",
                     "prompt-cache", "conversation-cache-mib", "conversation-cache-slots", "conversation-cache-min-free-mib",
                     "conversation-cache-min-tokens", "conversation-cache-disk-mib", "kv-resident", "ple-io", "ple-row-cache", "spec")
    arg_fields = ("--draft", "--spec", "--lookup", "--max-context", "--conversation-cache-mib", "--batch", "--kv",
                  "--vram-reserve-mib", "--prefill", "--short-read", "--kv-resident", "--conversation-cache-slots")
    env_fields = ("CUDA_DEVICE_ORDER", "FNX_NGRAM", "FNX_NGRAM_CACHE_MIB", "FNX_RING_F32", "FNX_ARENA_RESERVE_MIB",
                  "FNX_DF2_CONF", "FNX_DF2_TRACE", "STRATA_PF_W16_CACHE_MIB", "STRATA_BATCH_DF2")
    for arm_id in ("lapilli-mtp8", "sfnx-dflash2", "strata-dflash2-q4"):
        name = arm_id.split("-")[0] + "-config.json"
        config, source_config = load(root, "2026-11-25-flash-next-q8-engram/" + name)
        expected = pins["arms"][arm_id]["config_sha256"]
        if source_config["sha256"] != expected:
            raise ValueError(f"Config no longer matches the recorded campaign pin: {arm_id}")
        entry = {"id": arm_id, "original_config_sha256": expected}
        if "engine" in config:
            entry["engine"] = {key: config["engine"][key] for key in config_fields if key in config["engine"]}
            entry["kv"] = config["models"][0]["kv"]
        else:
            argv = config["args"]
            entry["engine"] = {key.removeprefix("--"): argv[argv.index(key) + 1] for key in arg_fields if key in argv}
        entry["environment"] = {key: config.get("env", {})[key] for key in env_fields if key in config.get("env", {})}
        parameters["arms"].append(entry)
    output("configs/2026-11-25/parameters.json", parameters)
    print("Wrote 10 aggregate quality rows and 3 parameter references. No raw fixtures or responses copied.")


if __name__ == "__main__":
    main()
