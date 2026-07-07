# Snyk debug.log Analyzer

`analyze_debug_log.py` parses a Snyk CLI `debug.log` (produced by running
`snyk test` with debug logging enabled) and emits a compact JSON summary of the
run's key diagnostic fields to **stdout**.

## What it extracts

| JSON field | Source in the log | Notes |
|------------|-------------------|-------|
| `exit_code` | line with `main - Exit Code:` | Integer CLI exit code. |
| `version` | line with `main - Version:` | Prefers the real value over `***` redactions. |
| `platform` | line with `main - Platform:` | Prefers the real value over `***`. |
| `api` | line with `main - API:` | e.g. `https://api.snyk.io`. |
| `region` | line with `main - Region:` | e.g. `snyk-us-01`. |
| `duration_sec` | `"durationMs"` JSON value | Milliseconds converted to seconds, 2 decimals. |
| `manifest_files` | every `Target file:` line | See **Manifest detection** below. |
| `manifest_count` | count of `Target file:` lines | `len(manifest_files)`. |
| `scanned_projects` | `"scannedProjects"` JSON value | Defaults to `0` if absent. |
| `skipped_manifest_files` | *derived* | `abs(manifest_count - scanned_projects)`. |
| `scan_status` | *derived* | `"completed"` if nothing skipped, else `"incomplete"`. |

Any field that cannot be located is emitted as `null` (except
`scanned_projects`, which defaults to `0`), so the script never crashes on a
partial or truncated log.

## Manifest detection approach

Manifest files are identified **exclusively from `Target file:` lines** that
appear throughout the log — one per project that the CLI actually targeted, e.g.:

```
Target file:       package-lock.json
Target file:       requirements.txt
```

For each such line, the text after the `Target file:` prefix is stripped of
surrounding whitespace and collected into the `manifest_files` array (in the
order it appears). `manifest_count` is simply the number of these lines.

> **Note:** An earlier revision read the manifest list from the
> `legacycli:2 - snyk-test auto detect manifest files [ ... ]` block. That
> source is **no longer used** — only `Target file:` lines drive the manifest
> list and count.

### Skipped manifests & scan status

`skipped_manifest_files` is the absolute difference between the number of
detected manifests and the number of `scannedProjects` reported by the CLI:

```
skipped_manifest_files = abs(manifest_count - scanned_projects)
```

If `scannedProjects` is missing from the log it defaults to `0`, which makes
every detected manifest count as skipped. `scan_status` is `"completed"` when
`skipped_manifest_files == 0`, otherwise `"incomplete"`.

## How to run

Requires **Python 3** (standard library only — no dependencies to install).

```bash
# Analyze the default ./debug.log
python3 analyze_debug_log.py

# Analyze a specific log file
python3 analyze_debug_log.py /path/to/debug.log
```

The `log_path` argument is optional and defaults to `debug.log` in the current
directory.

### Example output

```json
{
  "exit_code": 1,
  "version": "1.1305.2",
  "platform": "darwin arm64  TS_BINARY_WRAPPER/1.1305.2  node/26.3.1",
  "api": "https://api.snyk.io",
  "region": "snyk-us-01",
  "duration_sec": 4.77,
  "manifest_count": 2,
  "manifest_files": [
    "package-lock.json",
    "requirements.txt"
  ],
  "scanned_projects": 2,
  "skipped_manifest_files": 0,
  "scan_status": "completed"
}
```

To save the result to a file, redirect stdout:

```bash
python3 analyze_debug_log.py debug.log > analysis.json
```
