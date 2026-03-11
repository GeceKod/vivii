#!/usr/bin/env python3
"""
Generate per-country XMLTV files using the official iptv-org/epg project.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build XMLTV files from generated country channels.xml files.")
    parser.add_argument("--epg-repo", type=Path, required=True, help="Path to a cloned iptv-org/epg repository.")
    parser.add_argument("--channels-dir", type=Path, required=True, help="Directory containing country channels.xml files.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory where XMLTV files will be written.")
    parser.add_argument("--coverage-file", type=Path, default=None, help="Optional coverage.csv for ordering and metadata.")
    parser.add_argument("--max-connections", type=int, default=5, help="Parallel connections passed to iptv-org/epg.")
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="Optional JSON file describing successes and failures.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit non-zero if any country guide generation fails.",
    )
    return parser.parse_args()


def count_channels(xml_path: Path) -> int:
    root = ElementTree.parse(xml_path).getroot()
    return sum(1 for child in root.findall("channel"))


def load_coverage_order(coverage_file: Path | None) -> list[str]:
    if coverage_file is None or not coverage_file.exists():
        return []
    with coverage_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: (-int(row.get("channels_with_epg", "0")), row.get("output_group", "")))
    return [row["output_group"] for row in rows]


def resolve_channel_files(channels_dir: Path, coverage_file: Path | None) -> list[Path]:
    all_files = {path.stem: path for path in channels_dir.glob("*.xml")}
    ordered = []
    for output_group in load_coverage_order(coverage_file):
        key = output_group.replace(" ", "_")
        for stem, path in all_files.items():
            if stem == key:
                ordered.append(path)
                break
    remaining = [path for stem, path in sorted(all_files.items()) if path not in ordered]
    return ordered + remaining


def run_grab(epg_repo: Path, channels_file: Path, output_file: Path, max_connections: int) -> subprocess.CompletedProcess:
    command = [
        "npm",
        "run",
        "grab",
        "---",
        f"--channels={channels_file}",
        f"--output={output_file}",
        f"--maxConnections={max_connections}",
    ]
    return subprocess.run(
        command,
        cwd=epg_repo,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for existing in args.output_dir.glob("*.xml"):
        existing.unlink()

    summary = {"generated": [], "skipped": [], "failed": []}
    failures = 0

    for channels_file in resolve_channel_files(args.channels_dir, args.coverage_file):
        channel_count = count_channels(channels_file)
        output_file = args.output_dir / channels_file.name
        if channel_count == 0:
            summary["skipped"].append({"country": channels_file.stem, "reason": "no_channels"})
            continue

        result = run_grab(args.epg_repo, channels_file.resolve(), output_file.resolve(), args.max_connections)
        if result.returncode == 0 and output_file.exists():
            summary["generated"].append(
                {
                    "country": channels_file.stem,
                    "channels": channel_count,
                    "output": str(output_file),
                }
            )
            continue

        failures += 1
        summary["failed"].append(
            {
                "country": channels_file.stem,
                "channels": channel_count,
                "returncode": result.returncode,
                "stdout_tail": "\n".join(result.stdout.splitlines()[-20:]),
                "stderr_tail": "\n".join(result.stderr.splitlines()[-20:]),
            }
        )

    if args.summary_file is not None:
        args.summary_file.parent.mkdir(parents=True, exist_ok=True)
        args.summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "Generated {generated} XMLTV files, skipped {skipped}, failed {failed}.".format(
            generated=len(summary["generated"]),
            skipped=len(summary["skipped"]),
            failed=len(summary["failed"]),
        )
    )
    return 1 if failures and args.fail_on_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
