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
| `unscanned_manifest_count` | *derived* | See **Skipped manifests & scan status** below. |
| `unscanned_manifest` | every `Failed to get dependencies for` line | Manifests the CLI could not resolve; redaction-stripped and deduped. |
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

## Unscanned manifest detection

When the CLI cannot resolve a project's dependencies it names the manifest on a
`Failed to get dependencies for` line, followed by an `ERROR:` line with the
reason:

```
✗ Failed to get dependencies for ***/v_0.11.1/examples/example-clock/pom.xml
ERROR: Cannot build Maven dependency tree

✗ Failed to get dependencies for ***/v_0.11.1/examples/example-horizontalbar/package.json
ERROR: Missing node_modules folder: we can't test without dependencies.
```

Every such line is collected into `unscanned_manifest`, regardless of the reason
that follows — Maven (`Cannot build Maven dependency tree`), npm
(`Missing node_modules folder`), unparseable manifests and failed child processes
all mean the same thing: that manifest went unscanned. The reported path is the
text after the marker, with ANSI colour codes removed (some CLI versions colourise
these lines) and a leading `***/` working-directory redaction stripped, so the
examples above yield:

```
v_0.11.1/examples/example-clock/pom.xml
v_0.11.1/examples/example-horizontalbar/package.json
```

Paths are deduplicated and kept in first-seen order — the same manifest can fail
more than once in a single log. Redactions *inside* a path (e.g.
`src/main/re***s/...`) are left as-is, since the original text is unrecoverable.

### Skipped manifests & scan status

When `unscanned_manifest` is non-empty, `unscanned_manifest_count` is its length —
the manifests the CLI explicitly named as failures. Otherwise it falls back to the
absolute difference between the number of detected manifests and the number of
`scannedProjects` reported by the CLI:

```
unscanned_manifest_count = len(unscanned_manifest) or abs(manifest_count - scanned_projects)
```

If `scannedProjects` is missing from the log it defaults to `0`, which makes
every detected manifest count as skipped. `scan_status` is `"completed"` when
`unscanned_manifest_count == 0`, otherwise `"incomplete"`.

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
  "unscanned_manifest_count": 1,
  "unscanned_manifest": [
    "pom.xml"
  ],
  "scan_status": "incomplete"
}
```

To save the result to a file, redirect stdout:

```bash
python3 analyze_debug_log.py debug.log > analysis.json
```
