#!/usr/bin/env python3
"""Check accounting, report tables, local links, obvious secret patterns and hashes."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
GROUPS = {"local": 400, "humaneval": 328, "long_context": 6, "concurrency": 16, "tools_protocol": 216}


def files():
    return sorted(path for path in ROOT.rglob("*") if path.is_file()
                  and not any(part in (".git", "__pycache__") for part in path.relative_to(ROOT).parts)
                  and path != MANIFEST)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def numeric_tree(value):
    if isinstance(value, dict):
        for item in value.values():
            numeric_tree(item)
    elif isinstance(value, list):
        for item in value:
            numeric_tree(item)
    elif isinstance(value, float):
        check(math.isfinite(value), "Nonfinite JSON number")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true", help="Refresh checksums after all other checks pass")
    args = parser.parse_args()
    summary = json.loads((ROOT / "results/2026-11-26/summary.json").read_text())
    parameters = json.loads((ROOT / "configs/2026-11-25/parameters.json").read_text())
    report = (ROOT / "docs/reports/2026-11-26-v100-comparison.md").read_text()
    check(summary["schema_version"] == parameters["schema_version"] == 1, "Unknown schema")
    campaigns = {campaign["id"]: {arm["id"]: arm for arm in campaign["arms"]} for campaign in summary["campaigns"]}
    total = 0
    for arms in campaigns.values():
        for arm in arms.values():
            check(arm["graded"] == 966, "Wrong graded denominator")
            check(set(arm["groups"]) == set(GROUPS), "Missing or unexpected group")
            for name, denominator in GROUPS.items():
                group = arm["groups"][name]
                check(0 <= group["passed"] <= denominator, "Invalid group pass count")
                check(group.get("graded", denominator) == denominator, "Wrong group denominator")
            check(sum(group["passed"] for group in arm["groups"].values()) == arm["passed"], "Group total mismatch")
            total += 1
    q8 = next(campaign for campaign in summary["campaigns"] if campaign["id"] == "flash-next-q8-engram")
    for pair in q8["paired"]:
        check(sum(pair[key] for key in ("both_passed", "both_failed", "left_only_passed", "right_only_passed")) == 966,
              "Paired denominator mismatch")
        for side in ("left", "right"):
            check(pair["both_passed"] + pair[side + "_only_passed"] == campaigns[q8["id"]][pair[side]]["passed"],
                  "Paired outcome does not match arm")
    table_rows = {
        1: [("Strata (saved", "strata_saved"), ("Lapilli MTP8", "lapilli_mtp8"),
            ("sFNX DFlash2", "sfnx_dflash2"), ("sFNX MTP8", "sfnx_mtp8"), ("Lapilli MTP4", "lapilli_mtp4")],
        2: [("Nace", "nace"), ("ISTA", "ista")],
        3: [("Strata DFlash2", "strata-dflash2-q4"), ("Lapilli MTP8", "lapilli-mtp8"), ("sFNX DFlash2", "sfnx-dflash2")],
    }
    for section, campaign_id in ((1, "flash-next-initial"), (2, "lapilli-deepseek"), (3, "flash-next-q8-engram")):
        section_text = report.split(f"## {section}. ", 1)[1].split("\n## ", 1)[0]
        for prefix, arm_id in table_rows[section]:
            row = next(line for line in section_text.splitlines() if line.startswith("| " + prefix)
                       and len(line.split("|")[1:-1]) == 7)
            cells = [cell.strip().replace("**", "") for cell in row.split("|")[1:-1]]
            actual = [int(re.match(r"\d+", cell)[0]) for cell in cells[1:]]
            arm = campaigns[campaign_id][arm_id]
            expected = [arm["passed"]] + [arm["groups"][name]["passed"] for name in GROUPS]
            check(actual == expected, "Report table differs from curated data: " + arm_id)
    for arm in q8["arms"]:
        for digest in arm["pins"].values():
            check(re.fullmatch(r"[0-9a-f]{64}", digest) and digest in report, "Missing artifact pin in report")
    for arm in parameters["arms"]:
        check(arm["original_config_sha256"] == campaigns[q8["id"]][arm["id"]]["pins"]["config_sha256"],
              "Parameter reference has wrong original config pin")

    patterns = [
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{24,}"),
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
        re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+/"),
        re.compile(r"~/[A-Za-z]"),
        re.compile(r"https?://[^\s/]+:[^\s/@]+@"),
    ]
    for path in files():
        relative = path.relative_to(ROOT)
        check(not any(part in ("raw", "private") for part in relative.parts) and ".private." not in path.name,
              "Private artifact in publication tree: " + str(relative))
        text = path.read_text()
        for pattern in patterns:
            check(pattern.search(text) is None, "Possible credential or home path in " + str(relative))
        if path.suffix == ".json":
            numeric_tree(json.loads(text))
        if path.suffix == ".md":
            width = None
            for line in text.splitlines():
                if line.startswith("|"):
                    current = len(line.split("|"))
                    check(width is None or width == current, "Markdown table width mismatch: " + str(relative))
                    width = current
                else:
                    width = None
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                check(resolved.is_relative_to(ROOT) and resolved.exists(), "Broken or external local link: " + target)
    manifest = "".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(ROOT).as_posix() + "\n"
                       for path in files())
    if args.write_manifest:
        MANIFEST.write_text(manifest)
    else:
        check(MANIFEST.exists() and MANIFEST.read_text() == manifest, "Checksum manifest is missing or stale")
    print(f"Validated {total} quality rows, paired counts, parameter pins, report tables, local links and publication-file checksums.")
    print("Pattern checks are an additional check, not a substitute for reviewing the published files.")


if __name__ == "__main__":
    main()
