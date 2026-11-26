#!/usr/bin/env python3
"""Measure a shareable synthetic prompt on an already-loaded endpoint."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request
import uuid


def payload(model, rows, repeat, tag):
    prompt = f"Independent performance trial {tag}{rows}-{repeat}.\n"
    prompt += "\n".join(f"Record {i}: alpha beta gamma delta epsilon zeta eta theta." for i in range(rows))
    prompt += "\nWrite a detailed numbered checklist for reviewing a Python service, covering at least 40 items."
    return {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
        "presence_penalty": 1.5, "max_tokens": 256,
        "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": True},
        "stream": True, "stream_options": {"include_usage": True},
    }


def measure(endpoint, body, timeout):
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("BENCHMARK_API_KEY")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers=headers)
    start = time.monotonic()
    first = last = None
    usage, timings, finish = {}, {}, None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for line in response:
            if time.monotonic() - start > timeout:
                raise TimeoutError("Request exceeded its wall-time limit")
            if not line.startswith(b"data:"):
                continue
            raw = line[5:].strip()
            if raw == b"[DONE]":
                break
            chunk = json.loads(raw)
            if chunk.get("error"):
                raise RuntimeError("Endpoint returned an inference error; response text was not saved")
            usage = chunk.get("usage") or usage
            timing = chunk.get("timings")
            if isinstance(timing, dict):
                timings.update({key: value for key, value in timing.items()
                                if key in ("cache_n", "prompt_n", "prompt_ms", "prompt_per_second",
                                           "predicted_n", "predicted_ms", "predicted_per_second")
                                and isinstance(value, (int, float)) and not isinstance(value, bool)})
            for choice in chunk.get("choices", []):
                finish = choice.get("finish_reason") or finish
                delta = choice.get("delta") or {}
                if any(delta.get(key) for key in ("content", "reasoning_content", "reasoning")):
                    now = time.monotonic()
                    first = first if first is not None else now
                    last = now
    wall = time.monotonic() - start
    generated, prompt = usage.get("completion_tokens"), usage.get("prompt_tokens")
    if first is None or finish is None or not isinstance(generated, int) or not isinstance(prompt, int):
        raise RuntimeError("Incomplete response or missing usage; no benchmark row saved")
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
    return {
        "wall_s": wall, "client_ttft_s": first - start, "completion_tokens": generated,
        "prompt_tokens": prompt, "cached_tokens": cached,
        "stream_decode_tokens_per_s": (generated - 1) / (last - first) if last > first else None,
        "finish_reason": finish, "engine_timings_if_supplied": timings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18091/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--rows", type=int, nargs="+", default=[128, 512, 2048])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--trial-tag", default=None, help="Share one unique tag across engines for matched prompt text")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error("Use an http(s) base URL without credentials, query parameters or a fragment")
    if args.repeats < 1 or args.timeout <= 0 or any(rows < 1 for rows in args.rows):
        parser.error("Rows, repeats and timeout must be positive")
    if not args.dry_run and args.output is None:
        parser.error("--output is required unless --dry-run is selected")
    tag = args.trial_tag if args.trial_tag is not None else uuid.uuid4().hex[:12] + "-"
    requests = [(rows, repeat, payload(args.model, rows, repeat, tag))
                for rows in args.rows for repeat in range(args.repeats)]
    if args.dry_run:
        print(json.dumps({"requests": len(requests), "rows": args.rows, "repeats": args.repeats,
                          "max_completion_tokens_per_request": 256, "trial_tag": tag,
                          "network_requests_sent": 0}, indent=2))
        return
    # Refuse to overwrite earlier measurements. No credentials or generated text are written.
    with args.output.open("x") as output:
        for rows, repeat, body in requests:
            result = measure(args.base_url.rstrip("/") + "/chat/completions", body, args.timeout)
            result.update(schema_version=1, rows=rows, repeat=repeat, model=args.model, trial_tag=tag,
                          prompt_sha256=hashlib.sha256(body["messages"][0]["content"].encode()).hexdigest())
            output.write(json.dumps(result, allow_nan=False) + "\n")
            output.flush()
            print(json.dumps({key: result[key] for key in ("rows", "repeat", "prompt_tokens", "cached_tokens", "client_ttft_s", "wall_s")}))


if __name__ == "__main__":
    main()
