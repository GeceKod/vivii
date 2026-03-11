#!/usr/bin/env python3
"""
Assemble a GitHub Pages site from generated playlists, EPG files and reports.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a static site folder for GitHub Pages.")
    parser.add_argument("--site-dir", type=Path, required=True, help="Destination site directory.")
    parser.add_argument("--playlists-dir", type=Path, required=True, help="Directory containing generated .m3u8 playlists.")
    parser.add_argument("--epg-dir", type=Path, required=True, help="Directory containing generated .xml EPG files.")
    parser.add_argument("--reports-dir", type=Path, required=True, help="Directory containing CSV/JSON reports.")
    parser.add_argument("--coverage-file", type=Path, required=True, help="EPG coverage.csv file.")
    parser.add_argument("--pages-url", default="", help="Published GitHub Pages base URL.")
    parser.add_argument("--repo-url", default="", help="Repository URL for the index page.")
    return parser.parse_args()


def copy_tree(src_dir: Path, dst_dir: Path, pattern: str) -> list[Path]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for src_file in sorted(src_dir.glob(pattern)):
        dst_file = dst_dir / src_file.name
        shutil.copy2(src_file, dst_file)
        copied.append(dst_file)
    return copied


def read_coverage(coverage_file: Path) -> list[dict[str, str]]:
    with coverage_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: (-int(row.get("channels_with_epg", "0")), row.get("output_group", "")))
    return rows


def build_index_html(
    playlists: list[Path],
    epg_files: list[Path],
    coverage_rows: list[dict[str, str]],
    pages_url: str,
    repo_url: str,
) -> str:
    playlist_items = "\n".join(
        f'<li><a href="playlists/{html.escape(path.name)}">{html.escape(path.name)}</a></li>'
        for path in playlists[:150]
    )
    epg_items = "\n".join(
        f'<li><a href="epg/{html.escape(path.name)}">{html.escape(path.name)}</a></li>'
        for path in epg_files[:150]
    )
    coverage_rows_html = "\n".join(
        "<tr><td>{group}</td><td>{entries}</td><td>{channels}</td><td>{guides}</td></tr>".format(
            group=html.escape(row["output_group"]),
            entries=html.escape(row["entries"]),
            channels=html.escape(row["unique_tvg_ids"]),
            guides=html.escape(row["channels_with_epg"]),
        )
        for row in coverage_rows[:30]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vavoo Playlists</title>
  <style>
    :root {{
      --bg: #f4efe5;
      --ink: #1c1b1a;
      --muted: #6d655f;
      --card: #fffaf2;
      --line: #ded4c7;
      --accent: #0f6b5b;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: radial-gradient(circle at top, #fff8ee, var(--bg));
      color: var(--ink);
    }}
    main {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }}
    h1, h2 {{
      margin: 0 0 12px;
    }}
    p {{
      color: var(--muted);
      line-height: 1.5;
    }}
    .grid {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      margin-top: 24px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 12px 30px rgba(40, 32, 25, 0.06);
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    ul {{
      padding-left: 18px;
      max-height: 320px;
      overflow: auto;
      margin: 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: left;
      padding: 8px 6px;
      border-bottom: 1px solid var(--line);
    }}
    code {{
      background: #efe3d3;
      padding: 2px 6px;
      border-radius: 999px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Vavoo Playlists and EPG</h1>
    <p>GitHub Actions every 6 hours regenerates playlists, logos, manual overrides and country-based EPG inputs.</p>
    <p>Pages URL: <code>{html.escape(pages_url or "not set")}</code></p>
    <p>Repository: <a href="{html.escape(repo_url)}">{html.escape(repo_url or "not set")}</a></p>
    <div class="grid">
      <section class="card">
        <h2>Playlists</h2>
        <p>{len(playlists)} country playlists are published under <code>/playlists/</code>.</p>
        <ul>{playlist_items}</ul>
      </section>
      <section class="card">
        <h2>EPG XML</h2>
        <p>{len(epg_files)} generated XMLTV files are published under <code>/epg/</code>.</p>
        <ul>{epg_items}</ul>
      </section>
      <section class="card">
        <h2>EPG Coverage</h2>
        <table>
          <thead>
            <tr><th>Country</th><th>Entries</th><th>Tvg IDs</th><th>With EPG</th></tr>
          </thead>
          <tbody>
            {coverage_rows_html}
          </tbody>
        </table>
      </section>
    </div>
  </main>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    if args.site_dir.exists():
        shutil.rmtree(args.site_dir)
    args.site_dir.mkdir(parents=True, exist_ok=True)

    playlists = copy_tree(args.playlists_dir, args.site_dir / "playlists", "*.m3u8")
    epg_files = copy_tree(args.epg_dir, args.site_dir / "epg", "*.xml")
    reports_dst = args.site_dir / "reports"
    reports_dst.mkdir(parents=True, exist_ok=True)
    for src_name in ["summary.json", "channel_report.csv", "unresolved_channels.csv"]:
        src = args.reports_dir / src_name
        if src.exists():
            shutil.copy2(src, reports_dst / src.name)
    shutil.copy2(args.coverage_file, args.site_dir / "epg" / "coverage.csv")

    coverage_rows = read_coverage(args.coverage_file)
    index_html = build_index_html(playlists, epg_files, coverage_rows, args.pages_url, args.repo_url)
    (args.site_dir / "index.html").write_text(index_html, encoding="utf-8")
    (args.site_dir / ".nojekyll").write_text("", encoding="utf-8")

    manifest = {
        "playlists": [path.name for path in playlists],
        "epg": [path.name for path in epg_files],
        "coverage": coverage_rows,
        "pages_url": args.pages_url,
        "repo_url": args.repo_url,
    }
    (args.site_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Built Pages site with {len(playlists)} playlists and {len(epg_files)} EPG files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
