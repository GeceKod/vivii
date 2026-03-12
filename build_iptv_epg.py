#!/usr/bin/env python3
"""
Generate per-country XMLTV files using the official iptv-org/epg project.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import tempfile
from collections import defaultdict
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


def safe_fragment(value: str) -> str:
    fragment = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return fragment.strip("._-") or "item"


def tail_lines(text: str, line_count: int = 20) -> str:
    return "\n".join(text.splitlines()[-line_count:])


def inspect_xmltv(output_file: Path) -> dict[str, object]:
    info: dict[str, object] = {
        "exists": output_file.exists(),
        "size": output_file.stat().st_size if output_file.exists() else 0,
        "valid": False,
        "root_tag": "",
        "channels": 0,
        "programmes": 0,
        "parse_error": "",
    }
    if not output_file.exists():
        return info

    try:
        root = ElementTree.parse(output_file).getroot()
    except ElementTree.ParseError as exc:
        info["parse_error"] = str(exc)
        return info

    info["root_tag"] = root.tag
    info["channels"] = len(root.findall("channel"))
    info["programmes"] = len(root.findall("programme"))
    info["valid"] = root.tag == "tv"
    return info


def has_usable_epg(output_info: dict[str, object]) -> bool:
    return bool(output_info["valid"] and int(output_info["programmes"]) > 0)


def clone_element(element: ElementTree.Element) -> ElementTree.Element:
    return ElementTree.fromstring(ElementTree.tostring(element, encoding="unicode"))


def group_channels_by_site(channels_file: Path) -> dict[str, list[ElementTree.Element]]:
    root = ElementTree.parse(channels_file).getroot()
    grouped: dict[str, list[ElementTree.Element]] = defaultdict(list)
    for channel in root.findall("channel"):
        site = (channel.get("site") or "").strip() or "unknown"
        grouped[site].append(channel)
    return dict(grouped)


def write_channels_subset(elements: list[ElementTree.Element], output_file: Path) -> None:
    root = ElementTree.Element("channels")
    for element in elements:
        root.append(clone_element(element))
    tree = ElementTree.ElementTree(root)
    try:
        ElementTree.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(output_file, encoding="utf-8", xml_declaration=True)


def merge_xmltv_files(source_files: list[Path], output_file: Path) -> dict[str, object]:
    merged_root: ElementTree.Element | None = None
    seen_children: set[bytes] = set()

    for source_file in source_files:
        root = ElementTree.parse(source_file).getroot()
        if merged_root is None:
            merged_root = ElementTree.Element(root.tag, root.attrib)
        for child in root:
            signature = ElementTree.tostring(child, encoding="utf-8")
            if signature in seen_children:
                continue
            seen_children.add(signature)
            merged_root.append(ElementTree.fromstring(signature))

    if merged_root is None:
        merged_root = ElementTree.Element("tv")

    tree = ElementTree.ElementTree(merged_root)
    try:
        ElementTree.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    return inspect_xmltv(output_file)


def build_result_entry(
    country: str,
    channel_count: int,
    output_file: Path,
    status: str,
    mode: str,
    output_info: dict[str, object],
    bulk_result: subprocess.CompletedProcess | None = None,
    provider_results: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "country": country,
        "channels": channel_count,
        "output": str(output_file),
        "status": status,
        "mode": mode,
        "output_info": output_info,
    }
    if bulk_result is not None:
        entry["bulk_returncode"] = bulk_result.returncode
        entry["bulk_stdout_tail"] = tail_lines(bulk_result.stdout)
        entry["bulk_stderr_tail"] = tail_lines(bulk_result.stderr)
    if provider_results:
        entry["providers"] = provider_results
        entry["provider_counts"] = {
            "generated": sum(1 for provider in provider_results if provider["status"] == "generated"),
            "partial": sum(1 for provider in provider_results if provider["status"] == "partial"),
            "failed": sum(1 for provider in provider_results if provider["status"] == "failed"),
        }
    return entry


def generate_with_site_fallback(
    epg_repo: Path,
    channels_file: Path,
    output_file: Path,
    max_connections: int,
) -> dict[str, object]:
    grouped = group_channels_by_site(channels_file)
    provider_results: list[dict[str, object]] = []
    generated_outputs: list[Path] = []

    with tempfile.TemporaryDirectory(prefix=f"epg-{channels_file.stem}-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        providers_dir = temp_dir / "providers"
        providers_dir.mkdir(parents=True, exist_ok=True)

        total_sites = len(grouped)
        for provider_index, site in enumerate(sorted(grouped), start=1):
            elements = grouped[site]
            site_fragment = safe_fragment(site)
            provider_channels_file = providers_dir / f"{provider_index:03d}_{site_fragment}.channels.xml"
            provider_output_file = providers_dir / f"{provider_index:03d}_{site_fragment}.xml"
            write_channels_subset(elements, provider_channels_file)

            print(
                f"    [{provider_index}/{total_sites}] Fallback provider {site} with {len(elements)} channel rows...",
                flush=True,
            )
            result = run_grab(epg_repo, provider_channels_file.resolve(), provider_output_file.resolve(), max_connections)
            output_info = inspect_xmltv(provider_output_file)

            if result.returncode == 0 and has_usable_epg(output_info):
                status = "generated"
            elif has_usable_epg(output_info):
                status = "partial"
            else:
                status = "failed"

            provider_entry = {
                "site": site,
                "channels": len(elements),
                "status": status,
                "returncode": result.returncode,
                "output": str(provider_output_file),
                "output_info": output_info,
                "stdout_tail": tail_lines(result.stdout),
                "stderr_tail": tail_lines(result.stderr),
            }
            provider_results.append(provider_entry)

            if status in {"generated", "partial"}:
                generated_outputs.append(provider_output_file)
                print(
                    f"    [{provider_index}/{total_sites}] Recovered {site} with {output_info['programmes']} programmes.",
                    flush=True,
                )
            else:
                print(
                    f"    [{provider_index}/{total_sites}] Provider {site} failed with exit code {result.returncode}.",
                    flush=True,
                )

        if not generated_outputs:
            return {
                "status": "failed",
                "mode": "provider-fallback",
                "providers": provider_results,
                "output_info": inspect_xmltv(output_file),
            }

        merged_info = merge_xmltv_files(generated_outputs, output_file)
        status = "generated" if all(provider["status"] == "generated" for provider in provider_results) else "partial"
        return {
            "status": status,
            "mode": "provider-fallback",
            "providers": provider_results,
            "output_info": merged_info,
        }


def generate_country_xmltv(
    epg_repo: Path,
    channels_file: Path,
    output_file: Path,
    max_connections: int,
) -> dict[str, object]:
    channel_count = count_channels(channels_file)
    country = channels_file.stem

    result = run_grab(epg_repo, channels_file.resolve(), output_file.resolve(), max_connections)
    output_info = inspect_xmltv(output_file)
    if result.returncode == 0 and has_usable_epg(output_info):
        return build_result_entry(
            country=country,
            channel_count=channel_count,
            output_file=output_file,
            status="generated",
            mode="bulk",
            output_info=output_info,
            bulk_result=result,
        )

    if has_usable_epg(output_info):
        return build_result_entry(
            country=country,
            channel_count=channel_count,
            output_file=output_file,
            status="partial",
            mode="bulk-partial",
            output_info=output_info,
            bulk_result=result,
        )

    if output_file.exists():
        output_file.unlink()

    fallback = generate_with_site_fallback(epg_repo, channels_file, output_file, max_connections)
    if fallback["status"] == "failed" and output_file.exists():
        output_file.unlink()
    return build_result_entry(
        country=country,
        channel_count=channel_count,
        output_file=output_file,
        status=str(fallback["status"]),
        mode=str(fallback["mode"]),
        output_info=dict(fallback["output_info"]),
        bulk_result=result,
        provider_results=list(fallback.get("providers", [])),
    )


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for existing in args.output_dir.glob("*.xml"):
        existing.unlink()

    summary = {"generated": [], "partial": [], "skipped": [], "failed": []}
    failures = 0

    channel_files = resolve_channel_files(args.channels_dir, args.coverage_file)
    total_files = len(channel_files)

    for index, channels_file in enumerate(channel_files, start=1):
        channel_count = count_channels(channels_file)
        output_file = args.output_dir / channels_file.name
        if channel_count == 0:
            summary["skipped"].append({"country": channels_file.stem, "reason": "no_channels"})
            print(f"[{index}/{total_files}] Skipping {channels_file.stem}: no channels", flush=True)
            continue

        print(
            f"[{index}/{total_files}] Generating {channels_file.stem}.xml from {channel_count} matched channels...",
            flush=True,
        )
        result = generate_country_xmltv(args.epg_repo, channels_file, output_file, args.max_connections)

        if result["status"] == "generated":
            summary["generated"].append(result)
            print(
                f"[{index}/{total_files}] Completed {channels_file.stem}.xml with {result['output_info']['programmes']} programmes.",
                flush=True,
            )
            continue

        if result["status"] == "partial":
            summary["partial"].append(result)
            print(
                f"[{index}/{total_files}] Completed {channels_file.stem}.xml with partial recovery via {result['mode']}.",
                flush=True,
            )
            continue

        failures += 1
        summary["failed"].append(result)
        print(f"[{index}/{total_files}] Failed {channels_file.stem}.xml after bulk and fallback attempts.", flush=True)

    if args.summary_file is not None:
        args.summary_file.parent.mkdir(parents=True, exist_ok=True)
        args.summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "Generated {generated} XMLTV files, partial {partial}, skipped {skipped}, failed {failed}.".format(
            generated=len(summary["generated"]),
            partial=len(summary["partial"]),
            skipped=len(summary["skipped"]),
            failed=len(summary["failed"]),
        )
    )
    return 1 if failures and args.fail_on_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
