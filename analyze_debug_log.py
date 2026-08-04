#!/usr/bin/env python3
"""Analyze a Snyk CLI debug.log and emit key diagnostic fields as JSON to stdout."""

import argparse
import json
import re
import sys


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def find_value(lines, marker, prefer_non_redacted=False):
    """Return the stripped text after `marker` on the first matching line.

    When prefer_non_redacted is True, the first match whose value is not a `***`
    redaction is preferred; otherwise the first match wins. Returns None if no
    line contains the marker.
    """
    first = None
    for line in lines:
        idx = line.find(marker)
        if idx == -1:
            continue
        value = line[idx + len(marker):].strip()
        if first is None:
            first = value
        if not prefer_non_redacted:
            return value
        if not value.startswith("***"):
            return value
    return first


def parse_manifests(lines):
    """Collect manifest files from every line prefixed with `Target file:`.

    Returns a list of file paths in the order they appear (possibly empty). The
    count of these lines is the manifest count.
    """
    marker = "Target file:"
    files = []
    for line in lines:
        if line.lstrip().startswith(marker):
            value = line.split(marker, 1)[1].strip()
            if value:
                files.append(value)
    return files


def parse_unscanned_manifests(lines):
    """Collect manifests the CLI failed to resolve dependencies for.

    Each failure is reported as `✗ Failed to get dependencies for <path>` followed
    by an `ERROR:` line explaining why (missing node_modules, unbuildable Maven
    dependency tree, ...). Every such line counts regardless of the reason. The
    line may be wrapped in ANSI colour codes and the path is usually prefixed with
    a `***/` redaction of the working directory, both of which are stripped.

    Returns the paths in first-seen order, deduplicated (possibly empty).
    """
    marker = "Failed to get dependencies for "
    files = []
    seen = set()
    for line in lines:
        idx = line.find(marker)
        if idx == -1:
            continue
        value = ANSI_RE.sub("", line[idx + len(marker):]).strip()
        if value.startswith("***/"):
            value = value[len("***/"):]
        if value and value not in seen:
            seen.add(value)
            files.append(value)
    return files


def parse_int_json(lines, key):
    """Return the integer value for a JSON-style `"key": <int>` line, or None."""
    pattern = re.compile(r'"' + re.escape(key) + r'":\s*(\d+)')
    for line in lines:
        match = pattern.search(line)
        if match:
            return int(match.group(1))
    return None


def analyze(lines):
    exit_code = find_value(lines, "main - Exit Code:")
    manifest_files = parse_manifests(lines)
    unscanned_manifest = parse_unscanned_manifests(lines)
    scanned_projects = parse_int_json(lines, "scannedProjects")
    if scanned_projects is None:
        scanned_projects = 0

    manifest_count = len(manifest_files)
    # Named failures are authoritative when present; otherwise fall back to the
    # difference between detected manifests and projects the CLI reported scanning.
    unscanned = len(unscanned_manifest) or abs(manifest_count - scanned_projects)

    duration_ms = parse_int_json(lines, "durationMs")
    duration_sec = round(duration_ms / 1000, 2) if duration_ms is not None else None

    scan_status = "completed" if unscanned == 0 else "incomplete"

    return {
        "exit_code": int(exit_code) if exit_code and exit_code.lstrip("-").isdigit() else None,
        "version": find_value(lines, "main - Version:", prefer_non_redacted=True),
        "platform": find_value(lines, "main - Platform:", prefer_non_redacted=True),
        "api": find_value(lines, "main - API:", prefer_non_redacted=True),
        "region": find_value(lines, "main - Region:", prefer_non_redacted=True),
        "duration_sec": duration_sec,
        "manifest_count": manifest_count,
        "manifest_files": manifest_files,
        "scanned_projects": scanned_projects,
        "unscanned_manifest_count": unscanned,
        "unscanned_manifest": unscanned_manifest,
        "scan_status": scan_status,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze a Snyk CLI debug.log into JSON.")
    parser.add_argument("log_path", nargs="?", default="debug.log",
                        help="Path to the debug.log file (default: debug.log)")
    args = parser.parse_args()

    try:
        with open(args.log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as exc:
        print(f"error: could not read {args.log_path}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(analyze(lines), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
