#!/usr/bin/env python3
"""
Split Vavoo M3U playlists into one M3U8 per source group and assign categories.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape as xml_escape


ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "config" / "cache"
DEFAULT_INPUT = ROOT / "vavoo_full.m3u"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "country_m3u8"
DEFAULT_REPORT_DIR = ROOT / "output" / "reports"
DEFAULT_OVERRIDE_DIR = ROOT / "config" / "manual_overrides"
DEFAULT_EPG_DIR = ROOT / "output" / "epg"


def path_from_root(path: Path) -> str:
    resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)

IPTV_ORG_CHANNELS_URL = "https://iptv-org.github.io/api/channels.json"
IPTV_ORG_CATEGORIES_URL = "https://iptv-org.github.io/api/categories.json"
IPTV_ORG_COUNTRIES_URL = "https://iptv-org.github.io/api/countries.json"
IPTV_ORG_GUIDES_URL = "https://iptv-org.github.io/api/guides.json"
IPTV_ORG_LOGOS_URL = "https://iptv-org.github.io/api/logos.json"

SOURCE_GROUP_COUNTRIES = {
    "Albania": "AL",
    "Bulgaria": "BG",
    "France": "FR",
    "Germany": "DE",
    "Italy": "IT",
    "Netherlands": "NL",
    "Poland": "PL",
    "Portugal": "PT",
    "Romania": "RO",
    "Russia": "RU",
    "Spain": "ES",
    "Turkey": "TR",
    "United Kingdom": "GB",
    "United States": "US",
}

REGION_COUNTRIES = {
    "Arabia": {
        "AE",
        "BH",
        "DZ",
        "EG",
        "IQ",
        "JO",
        "KW",
        "LB",
        "LY",
        "MA",
        "OM",
        "PS",
        "QA",
        "SA",
        "SY",
        "TN",
        "YE",
    },
    "Balkans": {
        "AL",
        "BA",
        "BG",
        "GR",
        "HR",
        "ME",
        "MK",
        "RS",
        "SI",
        "XK",
    },
}

GROUP_PREFIXES = {
    "Albania": {"AL"},
    "Bulgaria": {"BG"},
    "France": {"FR"},
    "Germany": {"DE"},
    "Italy": {"IT"},
    "Netherlands": {"NL"},
    "Poland": {"PL"},
    "Portugal": {"PT"},
    "Romania": {"RO"},
    "Russia": {"RU"},
    "Spain": {"ES"},
    "Turkey": {"TR"},
    "United Kingdom": {"UK", "GB"},
    "United States": {"US", "USA"},
}

QUALITY_TOKENS = {
    "HD",
    "FHD",
    "UHD",
    "SD",
    "HEVC",
    "FULL",
    "RAW",
    "4K",
    "HQ",
    "LQ",
}

GENERIC_TOKENS = {
    "TV",
    "HD",
    "FHD",
    "UHD",
    "SD",
    "CHANNEL",
    "TELEVISION",
    "TELEVIZYON",
    "TELEVIZIJA",
    "TELE",
    "INT",
    "INTERNATIONAL",
    "PLUS",
    "LIVE",
    "ONLY",
    "DURING",
    "EVENTS",
}

TAG_CATEGORY_HINTS = {
    "KINDER": "Cocuk",
    "SPO": "Spor",
}

DB_CATEGORY_MAP = {
    "animation": "Cocuk",
    "auto": "Belgesel",
    "business": "Haber",
    "classic": "Film",
    "comedy": "Film",
    "cooking": "Yasam",
    "culture": "Belgesel",
    "documentary": "Belgesel",
    "education": "Egitim",
    "entertainment": "Eglence",
    "family": "Eglence",
    "general": "Ulusal",
    "kids": "Cocuk",
    "legislative": "Haber",
    "lifestyle": "Yasam",
    "movies": "Film",
    "music": "Muzik",
    "news": "Haber",
    "outdoor": "Belgesel",
    "religious": "Dini",
    "science": "Belgesel",
    "series": "Film",
    "shop": "Alisveris",
    "sports": "Spor",
    "travel": "Yasam",
    "weather": "Haber",
}

CATEGORY_PRIORITY = [
    "Spor",
    "Haber",
    "Cocuk",
    "Belgesel",
    "Film",
    "Muzik",
    "Dini",
    "Yasam",
    "Egitim",
    "Alisveris",
    "Eglence",
    "Ulusal",
]

KEYWORD_CATEGORY_RULES = [
    (
        "Haber",
        {
            "NEWS",
            "HABER",
            "CNN",
            "EURONEWS",
            "ALJAZEERA",
            "AL JAZEERA",
            "BLOOMBERG",
            "CNBC",
            "FRANCE 24",
            "SKY NEWS",
            "BBC NEWS",
            "FOX NEWS",
            "TGRT HABER",
            "TRT HABER",
            "SOZCU",
            "NTV",
            "A PARA",
            "BUSINESS",
        },
    ),
    (
        "Cocuk",
        {
            "KIDS",
            "KID",
            "KINDER",
            "JR",
            "JUNIOR",
            "BABY",
            "CARTOON",
            "TOON",
            "BOOMERANG",
            "NICK",
            "DISNEY",
            "MINIKA",
            "MINICA",
            "DUCK",
            "COCUK",
            "COCUK",
            "ANIME",
            "TAYO",
            "SPONGEBOB",
            "PEDIA",
        },
    ),
    (
        "Belgesel",
        {
            "DOCUMENTARY",
            "BELGESEL",
            "DISCOVERY",
            "NAT GEO",
            "NATIONAL GEOGRAPHIC",
            "ANIMAL PLANET",
            "HISTORY",
            "BBC EARTH",
            "SCIENCE",
            "DOCU",
            "EXPLORE",
            "NATURE",
            "WILD",
            "TRAVEL",
            "PLANET",
            "ODYSSEY",
        },
    ),
    (
        "Film",
        {
            "MOVIE",
            "MOVIES",
            "FILM",
            "FILMBOX",
            "SINEMA",
            "CINEMA",
            "CINEMAX",
            "SERIES",
            "SERIJE",
            "DRAMA",
            "AMC",
            "AXN",
            "HBO",
            "SHOWCASE",
            "THRILLER",
            "HORROR",
            "ROMANCE",
            "ACTION",
            "COMEDY",
            "DIZI",
            "FOX CRIME",
            "FOX LIFE",
            "PARAMOUNT",
            "SYFY",
        },
    ),
    (
        "Spor",
        {
            "SPORT",
            "SPORTS",
            "SPOR",
            "EUROSPORT",
            "ESPN",
            "ARENA SPORT",
            "SUPERSPORT",
            "BEIN SPORT",
            "BEIN SPORTS",
            "DAZN",
            "MATCH",
            "FUTBOL",
            "NBA",
            "NFL",
            "SSC",
            "RACING",
            "FIGHT",
            "GOLF",
            "TENNIS",
            "SPORTKLUB",
            "TIVIBU SPOR",
            "SPOR SMART",
            "S SPORT",
            "PREMIER SPORTS",
        },
    ),
    (
        "Muzik",
        {
            "MUSIC",
            "MUZIK",
            "MTV",
            "VH1",
            "KRAL",
            "POWER",
            "NUMBER 1",
            "HITS",
            "DREAM TURK",
            "MEZZO",
            "MCM",
            "MELODY",
            "MUSICBOX",
        },
    ),
    (
        "Dini",
        {
            "ISLAM",
            "KURAN",
            "QURAN",
            "QURAN",
            "RELIGION",
            "SEMERKAND",
            "NOOR",
            "HIDAYAH",
            "MADANI",
            "SALAM",
            "QUR",
        },
    ),
    (
        "Yasam",
        {
            "KITCHEN",
            "FOOD",
            "COOK",
            "HGTV",
            "HOME",
            "LIFE",
            "STYLE",
            "TLC",
            "TRAVEL",
            "GARDEN",
            "FASHION",
            "WEDDING",
            "LIVING",
        },
    ),
    (
        "Egitim",
        {
            "EBA",
            "EDU",
            "ACADEMY",
            "SCHOOL",
            "UNIVERSITY",
            "LEARN",
            "KNOWLEDGE",
            "CLASSROOM",
        },
    ),
    (
        "Alisveris",
        {
            "SHOP",
            "QVC",
            "JTV",
            "123 TV",
            "1 2 3 TV",
            "SHOPPING",
        },
    ),
]


@dataclass(frozen=True)
class SourceEntry:
    source_group: str
    raw_name: str
    clean_name: str
    url: str
    tags: tuple[str, ...]


@dataclass
class DbChannel:
    channel_id: str
    name: str
    country: str | None
    categories: list[str]
    website: str | None
    logo_url: str | None
    variants: set[str]
    compact_variants: set[str]
    informative_tokens: set[str]


@dataclass
class MatchResult:
    channel: DbChannel | None
    score: float
    reason: str | None


@dataclass
class ManualOverride:
    category: str | None
    country_code: str | None
    logo_url: str | None
    tvg_id: str | None
    matched_name: str | None
    matched_country: str | None
    website: str | None
    notes: str | None


@dataclass(frozen=True)
class GuideEntry:
    channel_id: str
    site: str
    site_id: str
    site_name: str
    lang: str
    feed: str | None


def ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def normalize_name(value: str) -> str:
    value = ascii_fold(value).upper().strip()
    value = re.sub(r"\s+\.[A-Z0-9]+$", "", value)
    value = value.replace("&", " AND ")
    value = value.replace("+", " PLUS ")
    value = re.sub(r"[`'’]", "", value)
    value = re.sub(r"[(){}\[\],./\\|:_-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def compact_name(value: str) -> str:
    return normalize_name(value).replace(" ", "")


def clean_channel_name(raw_name: str) -> str:
    clean = re.sub(r"\s+\.[A-Za-z0-9]+$", "", raw_name.strip())
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def extract_tags(raw_name: str) -> tuple[str, ...]:
    tags = []
    for tag in re.findall(r"\[([^\]]+)\]", raw_name):
        folded = ascii_fold(tag).upper().strip()
        if folded:
            tags.append(folded)
    return tuple(tags)


def strip_quality_tokens(text: str) -> str:
    tokens = [token for token in normalize_name(text).split() if token not in QUALITY_TOKENS]
    return " ".join(tokens)


def manual_key(name: str, source_group: str) -> str:
    normalized = strip_quality_tokens(clean_channel_name(name))
    normalized = re.sub(r"^\[[^\]]+\]\s*", "", normalized).strip()
    tokens = normalized.split()
    prefixes = GROUP_PREFIXES.get(source_group, set())
    if len(tokens) > 1 and tokens[0] in prefixes:
        normalized = " ".join(tokens[1:])
    return normalized or normalize_name(clean_channel_name(name))


def make_variants(name: str, prefixes: Iterable[str] = ()) -> set[str]:
    variants = set()

    def add_variant(value: str) -> None:
        normalized = strip_quality_tokens(value)
        if not normalized:
            return
        variants.add(normalized)
        compact = normalized.replace(" ", "")
        if compact:
            variants.add(compact)
        lean_tokens = [token for token in normalized.split() if token not in GENERIC_TOKENS]
        if lean_tokens:
            lean = " ".join(lean_tokens)
            variants.add(lean)
            variants.add("".join(lean_tokens))

    add_variant(name)
    add_variant(re.sub(r"^\[[^\]]+\]\s*", "", name))
    add_variant(re.sub(r"\[[^\]]+\]", " ", name))

    normalized = strip_quality_tokens(name)
    tokens = normalized.split()
    if len(tokens) > 1 and tokens[0] in prefixes:
        add_variant(" ".join(tokens[1:]))

    return {variant for variant in variants if len(variant) >= 2}


def informative_tokens(name: str) -> set[str]:
    tokens = set()
    for token in normalize_name(name).split():
        if len(token) < 3:
            continue
        if token in QUALITY_TOKENS or token in GENERIC_TOKENS:
            continue
        tokens.add(token)
    return tokens


def http_get_json(url: str) -> object:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def load_remote_json(url: str, cache_path: Path, refresh: bool) -> object:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))

    try:
        payload = http_get_json(url)
    except URLError:
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        raise

    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_country_names(payload: list[dict]) -> dict[str, str]:
    names = {}
    for item in payload:
        code = (item.get("code") or "").strip().upper()
        name = (item.get("name") or "").strip()
        if code and name:
            names[code] = name
    for source_group, code in SOURCE_GROUP_COUNTRIES.items():
        names[code] = source_group
    return names


def logo_preference(item: dict) -> tuple[int, int, int, int]:
    feed_rank = 1 if item.get("feed") in {None, ""} else 0
    tag_rank = 1 if not item.get("tags") else 0
    format_rank = {"SVG": 3, "PNG": 2, "WEBP": 1, "JPG": 0, "JPEG": 0}.get(
        str(item.get("format", "")).upper(),
        0,
    )
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    return (feed_rank, tag_rank, format_rank, width * height)


def build_logo_index(payload: list[dict]) -> dict[str, str]:
    selected: dict[str, dict] = {}
    for item in payload:
        channel_id = (item.get("channel") or "").strip()
        logo_url = (item.get("url") or "").strip()
        if not channel_id or not logo_url:
            continue
        current = selected.get(channel_id)
        if current is None or logo_preference(item) > logo_preference(current):
            selected[channel_id] = item
    return {channel_id: item["url"] for channel_id, item in selected.items()}


def build_guide_index(payload: list[dict]) -> dict[str, list[GuideEntry]]:
    guide_index: dict[str, list[GuideEntry]] = defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()
    for item in payload:
        channel_id = (item.get("channel") or "").strip()
        site = (item.get("site") or "").strip()
        site_id = (item.get("site_id") or "").strip()
        lang = (item.get("lang") or "").strip()
        if not channel_id or not site or not site_id or not lang:
            continue
        key = (channel_id, site, site_id, lang)
        if key in seen:
            continue
        seen.add(key)
        guide_index[channel_id].append(
            GuideEntry(
                channel_id=channel_id,
                site=site,
                site_id=site_id,
                site_name=(item.get("site_name") or "").strip(),
                lang=lang,
                feed=(item.get("feed") or "").strip() or None,
            )
        )
    for channel_id in guide_index:
        guide_index[channel_id].sort(key=lambda guide: (guide.lang, guide.site, guide.site_id))
    return guide_index


def parse_m3u(path: Path) -> list[SourceEntry]:
    entries = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF"):
            continue
        match = re.search(r'group-title="([^"]+)"', line)
        if not match:
            continue
        if index + 1 >= len(lines):
            continue
        url = lines[index + 1].strip()
        raw_name = line.split(",", 1)[1].strip()
        entries.append(
            SourceEntry(
                source_group=match.group(1).strip(),
                raw_name=raw_name,
                clean_name=clean_channel_name(raw_name),
                url=url,
                tags=extract_tags(raw_name),
            )
        )
    return entries


def build_db_channels(
    payload: list[dict],
    logo_index: dict[str, str],
) -> tuple[list[DbChannel], dict[str, list[int]], dict[str, set[int]]]:
    exact_index: dict[str, list[int]] = defaultdict(list)
    token_index: dict[str, set[int]] = defaultdict(set)
    db_channels: list[DbChannel] = []

    for raw_channel in payload:
        names = [raw_channel.get("name", "")]
        names.extend(raw_channel.get("alt_names") or [])
        variants = set()
        informative = set()
        for name in names:
            if not name:
                continue
            variants.update(make_variants(name))
            informative.update(informative_tokens(name))
        if not variants:
            continue
        compact_variants = {variant.replace(" ", "") for variant in variants}
        channel = DbChannel(
            channel_id=raw_channel.get("id", "").strip(),
            name=raw_channel.get("name", "").strip(),
            country=raw_channel.get("country"),
            categories=list(raw_channel.get("categories") or []),
            website=raw_channel.get("website"),
            logo_url=logo_index.get(raw_channel.get("id", "").strip()),
            variants=variants,
            compact_variants=compact_variants,
            informative_tokens=informative,
        )
        db_index = len(db_channels)
        db_channels.append(channel)
        for variant in variants | compact_variants:
            exact_index[variant].append(db_index)
        for token in informative:
            token_index[token].add(db_index)

    return db_channels, exact_index, token_index


def region_preference(source_group: str) -> set[str]:
    preferred = set()
    group_country = SOURCE_GROUP_COUNTRIES.get(source_group)
    if group_country:
        preferred.add(group_country)
    preferred.update(REGION_COUNTRIES.get(source_group, set()))
    return preferred


def score_match(entry: SourceEntry, source_variants: set[str], channel: DbChannel) -> float:
    best_score = 0.0
    source_compacts = {variant.replace(" ", "") for variant in source_variants}
    for source_variant in source_variants:
        source_tokens = set(source_variant.split())
        for db_variant in channel.variants:
            db_tokens = set(db_variant.split())
            seq_ratio = SequenceMatcher(None, source_variant, db_variant).ratio()
            compact_ratio = SequenceMatcher(
                None, source_variant.replace(" ", ""), db_variant.replace(" ", "")
            ).ratio()
            token_ratio = len(source_tokens & db_tokens) / max(1, len(source_tokens | db_tokens))
            contains_bonus = 0.0
            if source_variant in db_variant or db_variant in source_variant:
                contains_bonus = 0.06
            best_score = max(best_score, compact_ratio * 0.55 + seq_ratio * 0.25 + token_ratio * 0.20 + contains_bonus)

    if source_compacts & channel.compact_variants:
        best_score += 0.10

    preferred_countries = region_preference(entry.source_group)
    if channel.country in preferred_countries:
        best_score += 0.08
    elif SOURCE_GROUP_COUNTRIES.get(entry.source_group) and channel.country:
        best_score -= 0.03

    tag_category = tag_category_hint(entry.tags)
    db_category = category_from_db(channel.categories)
    if tag_category and db_category == tag_category:
        best_score += 0.03

    return min(best_score, 1.10)


def collect_candidates(
    entry: SourceEntry,
    source_variants: set[str],
    exact_index: dict[str, list[int]],
    token_index: dict[str, set[int]],
    allow_fuzzy: bool,
) -> tuple[set[int], str | None]:
    exact_candidates: set[int] = set()
    for variant in source_variants:
        exact_candidates.update(exact_index.get(variant, []))
        exact_candidates.update(exact_index.get(variant.replace(" ", ""), []))
    if exact_candidates:
        return exact_candidates, "iptv-org-exact"
    if not allow_fuzzy:
        return set(), None

    tokens = sorted(
        {
            token
            for variant in source_variants
            for token in informative_tokens(variant)
        },
        key=lambda item: (-len(item), item),
    )
    candidate_counts: Counter[int] = Counter()
    for token in tokens[:4]:
        candidate_counts.update(token_index.get(token, set()))
        if len(candidate_counts) >= 800:
            break
    if not candidate_counts:
        return set(), None

    minimum_overlap = 2 if len(tokens) >= 2 else 1
    fuzzy_candidates = {
        candidate_id for candidate_id, count in candidate_counts.items() if count >= minimum_overlap
    }
    if not fuzzy_candidates:
        fuzzy_candidates = {
            candidate_id for candidate_id, _count in candidate_counts.most_common(300)
        }
    return fuzzy_candidates, "iptv-org-fuzzy"


def find_best_match(
    entry: SourceEntry,
    db_channels: list[DbChannel],
    exact_index: dict[str, list[int]],
    token_index: dict[str, set[int]],
    allow_fuzzy: bool,
) -> MatchResult:
    prefixes = GROUP_PREFIXES.get(entry.source_group, set())
    source_variants = make_variants(entry.clean_name, prefixes=prefixes)
    if not source_variants:
        return MatchResult(channel=None, score=0.0, reason=None)

    candidate_ids, initial_reason = collect_candidates(
        entry,
        source_variants,
        exact_index,
        token_index,
        allow_fuzzy=allow_fuzzy,
    )
    if not candidate_ids:
        return MatchResult(channel=None, score=0.0, reason=None)

    preferred_countries = region_preference(entry.source_group)
    if preferred_countries and len(candidate_ids) > 40:
        preferred_candidates = {
            candidate_id
            for candidate_id in candidate_ids
            if db_channels[candidate_id].country in preferred_countries
        }
        if preferred_candidates:
            candidate_ids = preferred_candidates

    scored = []
    for channel_id in candidate_ids:
        channel = db_channels[channel_id]
        score = score_match(entry, source_variants, channel)
        scored.append((score, channel))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_channel = scored[0]

    expected_country = SOURCE_GROUP_COUNTRIES.get(entry.source_group)
    if (
        expected_country
        and best_channel.country
        and best_channel.country != expected_country
        and initial_reason == "iptv-org-exact"
    ):
        has_expected_candidate = any(
            db_channels[candidate_id].country == expected_country for candidate_id in candidate_ids
        )
        distinct_tokens = informative_tokens(entry.clean_name)
        token_lengths = sorted(len(token) for token in distinct_tokens)
        is_generic_short_name = (
            len(distinct_tokens) <= 1
            or (len(distinct_tokens) == 2 and token_lengths and token_lengths[-1] <= 4)
        )
        if not has_expected_candidate and is_generic_short_name:
            return MatchResult(channel=None, score=best_score, reason=None)

    threshold = 0.92 if initial_reason == "iptv-org-exact" else 0.82
    if best_score < threshold:
        return MatchResult(channel=None, score=best_score, reason=None)
    return MatchResult(channel=best_channel, score=best_score, reason=initial_reason)


def category_from_db(categories: list[str]) -> str | None:
    mapped = [DB_CATEGORY_MAP[category] for category in categories if category in DB_CATEGORY_MAP]
    if not mapped:
        return None
    counts = Counter(mapped)
    return min(
        counts,
        key=lambda category: (-counts[category], CATEGORY_PRIORITY.index(category)),
    )


def keyword_category_hint(name: str) -> str | None:
    normalized = normalize_name(name)
    if not normalized:
        return None
    padded = f" {normalized} "
    for category, keywords in KEYWORD_CATEGORY_RULES:
        for keyword in keywords:
            normalized_keyword = normalize_name(keyword)
            if not normalized_keyword:
                continue
            if f" {normalized_keyword} " in padded:
                return category
    return None


def tag_category_hint(tags: tuple[str, ...]) -> str | None:
    for tag in tags:
        for tag_key, category in TAG_CATEGORY_HINTS.items():
            if tag_key in tag:
                return category
    return None


def resolve_category(entry: SourceEntry, match: MatchResult) -> tuple[str, str]:
    db_category = category_from_db(match.channel.categories) if match.channel else None
    keyword_category = keyword_category_hint(entry.clean_name)
    tag_category = tag_category_hint(entry.tags)

    if keyword_category and db_category in {None, "Ulusal", "Eglence"}:
        return keyword_category, "keyword"
    if keyword_category == "Haber" and db_category in {"Spor", "Ulusal", "Eglence"}:
        return keyword_category, "keyword"
    if keyword_category == "Belgesel" and db_category in {"Spor", "Ulusal", "Eglence"}:
        return keyword_category, "keyword"
    if keyword_category == "Film" and db_category in {"Spor", "Ulusal", "Eglence", "Cocuk"}:
        return keyword_category, "keyword"
    if keyword_category == "Yasam" and db_category in {"Spor", "Ulusal"}:
        return keyword_category, "keyword"
    if db_category:
        return db_category, match.reason or "iptv-org"
    if keyword_category:
        return keyword_category, "keyword"
    if tag_category:
        return tag_category, "tag"
    return "Ulusal", "default"


def resolve_country_info(
    entry: SourceEntry,
    match: MatchResult,
    country_names: dict[str, str],
) -> tuple[str, str]:
    source_code = SOURCE_GROUP_COUNTRIES.get(entry.source_group, "")
    if source_code:
        return source_code, country_names.get(source_code, entry.source_group)
    if match.channel and match.channel.country:
        code = match.channel.country
        return code, country_names.get(code, code)
    return "", entry.source_group


def load_manual_overrides(overrides_dir: Path) -> dict[tuple[str, str], ManualOverride]:
    overrides: dict[tuple[str, str], ManualOverride] = {}
    if not overrides_dir.exists():
        return overrides

    for csv_path in sorted(overrides_dir.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            has_override_columns = any(name.startswith("override_") for name in fieldnames)
            for row in reader:
                source_group = (row.get("source_group") or "").strip()
                clean_name = (row.get("clean_name") or "").strip()
                if not source_group or not clean_name:
                    continue
                if has_override_columns:
                    category = (row.get("override_category") or "").strip() or None
                    country_code = (row.get("override_country_code") or "").strip().upper() or None
                    logo_url = (row.get("override_logo_url") or "").strip() or None
                    tvg_id = (row.get("override_tvg_id") or "").strip() or None
                    matched_name = (row.get("override_matched_name") or "").strip() or None
                    matched_country = (row.get("override_matched_country") or "").strip().upper() or None
                    website = (row.get("override_website") or "").strip() or None
                else:
                    category = (row.get("category") or "").strip() or None
                    country_code = (
                        row.get("country_code")
                        or row.get("resolved_country_code")
                        or ""
                    ).strip().upper() or None
                    logo_url = (row.get("logo_url") or "").strip() or None
                    tvg_id = (row.get("tvg_id") or "").strip() or None
                    matched_name = (row.get("matched_name") or "").strip() or None
                    matched_country = (row.get("matched_country") or "").strip().upper() or None
                    website = (row.get("matched_website") or "").strip() or None
                notes = (row.get("notes") or "").strip() or None
                if not any([category, country_code, logo_url, tvg_id, matched_name, matched_country, website, notes]):
                    continue
                overrides[(source_group, manual_key(clean_name, source_group))] = ManualOverride(
                    category=category,
                    country_code=country_code,
                    logo_url=logo_url,
                    tvg_id=tvg_id,
                    matched_name=matched_name,
                    matched_country=matched_country,
                    website=website,
                    notes=notes,
                )
    return overrides


def apply_manual_override(
    record: dict[str, str],
    override: ManualOverride | None,
    country_names: dict[str, str],
    logo_index: dict[str, str],
    channels_by_id: dict[str, DbChannel],
) -> dict[str, str]:
    if override is None:
        return record

    updated = dict(record)
    if override.category:
        updated["category"] = override.category
        updated["category_source"] = "manual"
    if override.country_code:
        updated["resolved_country_code"] = override.country_code
        updated["resolved_country_name"] = country_names.get(override.country_code, override.country_code)
        updated["output_group"] = updated["resolved_country_name"]
    if override.tvg_id:
        updated["matched_id"] = override.tvg_id
        updated["match_reason"] = "manual"
        updated["match_score"] = updated["match_score"] or "1.000"
        db_channel = channels_by_id.get(override.tvg_id)
        if db_channel is not None:
            updated["matched_name"] = db_channel.name
            updated["matched_country"] = db_channel.country or updated["matched_country"]
            updated["matched_country_name"] = (
                country_names.get(db_channel.country, db_channel.country)
                if db_channel.country
                else updated["matched_country_name"]
            )
            updated["matched_website"] = db_channel.website or updated["matched_website"]
            if not override.category:
                db_category = category_from_db(db_channel.categories)
                if db_category and updated["category_source"] in {"default", "tag"}:
                    updated["category"] = db_category
                    updated["category_source"] = "manual-id"
                elif db_category and updated["category"] in {"Ulusal", "Eglence"}:
                    updated["category"] = db_category
                    updated["category_source"] = "manual-id"
    if override.matched_name:
        updated["matched_name"] = override.matched_name
        updated["match_reason"] = "manual"
    if override.matched_country:
        updated["matched_country"] = override.matched_country
        updated["matched_country_name"] = country_names.get(override.matched_country, override.matched_country)
        updated["match_reason"] = "manual"
    if override.website:
        updated["matched_website"] = override.website
    if override.logo_url:
        updated["logo_url"] = override.logo_url
    elif override.tvg_id and override.tvg_id in logo_index:
        updated["logo_url"] = logo_index[override.tvg_id]
    if override.notes:
        updated["manual_notes"] = override.notes
    if override.category or override.country_code or override.logo_url or override.tvg_id:
        updated["manual_override"] = "1"
    return updated


def safe_file_fragment(value: str) -> str:
    folded = ascii_fold(value)
    folded = re.sub(r"[^A-Za-z0-9]+", "_", folded).strip("_")
    return folded or "unknown"


def attr_escape(value: str) -> str:
    return value.replace('"', "'")


def write_m3u8_files(records: list[dict], output_dir: Path, epg_url_map: dict[str, str] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing_file in output_dir.glob("*.m3u8"):
        existing_file.unlink()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["output_group"]].append(record)

    for output_group, rows in grouped.items():
        filename = output_dir / f"vavoo_{safe_file_fragment(output_group)}.m3u8"
        rows.sort(key=lambda row: (CATEGORY_PRIORITY.index(row["category"]), normalize_name(row["clean_name"])))
        with filename.open("w", encoding="utf-8", newline="\n") as handle:
            epg_url = (epg_url_map or {}).get(output_group, "")
            if epg_url:
                handle.write(f'#EXTM3U x-tvg-url="{attr_escape(epg_url)}"\n')
            else:
                handle.write("#EXTM3U\n")
            for row in rows:
                attrs = [
                    '-1',
                    f'tvg-name="{attr_escape(row["clean_name"])}"',
                    f'tvg-country="{attr_escape(row["resolved_country_code"] or row["source_group"])}"',
                    f'group-title="{attr_escape(row["category"])}"',
                ]
                if row["matched_id"]:
                    attrs.append(f'tvg-id="{attr_escape(row["matched_id"])}"')
                if row["logo_url"]:
                    attrs.append(f'tvg-logo="{attr_escape(row["logo_url"])}"')
                handle.write(f'#EXTINF:{" ".join(attrs)},{row["raw_name"]}\n')
                handle.write(f'{row["url"]}\n')


def build_epg_url_map(
    records: list[dict],
    epg_base_url: str | None,
    existing_epg_dir: Path | None = None,
) -> dict[str, str]:
    if not epg_base_url:
        return {}
    base = epg_base_url.rstrip("/")
    output_groups = {
        record["output_group"]
        for record in records
        if record["matched_id"] and int(record.get("epg_guides_count", "0") or "0") > 0
    }
    url_map = {}
    for output_group in output_groups:
        fragment = safe_file_fragment(output_group)
        if existing_epg_dir is not None and not (existing_epg_dir / f"{fragment}.xml").exists():
            continue
        url_map[output_group] = f"{base}/{fragment}.xml"
    return url_map


def write_epg_files(records: list[dict], epg_dir: Path, guide_index: dict[str, list[GuideEntry]]) -> None:
    epg_dir.mkdir(parents=True, exist_ok=True)
    channels_dir = epg_dir / "channels"
    public_dir = epg_dir / "public"
    channels_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    for existing_file in channels_dir.glob("*.xml"):
        existing_file.unlink()

    grouped_records: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped_records[record["output_group"]].append(record)

    coverage_rows = []
    index_payload = {}

    for output_group, rows in grouped_records.items():
        unique_channels = {}
        for row in rows:
            matched_id = row["matched_id"]
            if matched_id and matched_id not in unique_channels:
                unique_channels[matched_id] = row

        guide_rows = []
        channels_with_epg = 0
        for matched_id, row in sorted(unique_channels.items(), key=lambda item: normalize_name(item[1]["clean_name"])):
            guides = guide_index.get(matched_id, [])
            if not guides:
                continue
            channels_with_epg += 1
            display_name = row["matched_name"] or row["clean_name"]
            for guide in guides:
                guide_rows.append(
                    '  <channel site="{site}" site_id="{site_id}" lang="{lang}" xmltv_id="{xmltv_id}">{name}</channel>'.format(
                        site=xml_escape(guide.site),
                        site_id=xml_escape(guide.site_id),
                        lang=xml_escape(guide.lang),
                        xmltv_id=xml_escape(matched_id),
                        name=xml_escape(display_name),
                    )
                )

        channels_path = channels_dir / f"{safe_file_fragment(output_group)}.xml"
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<channels>"]
        xml_lines.extend(guide_rows)
        xml_lines.append("</channels>")
        channels_path.write_text("\n".join(xml_lines) + "\n", encoding="utf-8")

        coverage_rows.append(
            {
                "output_group": output_group,
                "entries": str(len(rows)),
                "unique_tvg_ids": str(len(unique_channels)),
                "channels_with_epg": str(channels_with_epg),
                "guide_rows": str(len(guide_rows)),
                "channels_xml": path_from_root(channels_path),
                "expected_xmltv_output": path_from_root(public_dir / f"{safe_file_fragment(output_group)}.xml"),
            }
        )
        index_payload[output_group] = {
            "channels_xml": path_from_root(channels_path),
            "expected_xmltv_output": path_from_root(public_dir / f"{safe_file_fragment(output_group)}.xml"),
            "unique_tvg_ids": len(unique_channels),
            "channels_with_epg": channels_with_epg,
            "guide_rows": len(guide_rows),
        }

    coverage_path = epg_dir / "coverage.csv"
    with coverage_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "output_group",
                "entries",
                "unique_tvg_ids",
                "channels_with_epg",
                "guide_rows",
                "channels_xml",
                "expected_xmltv_output",
            ],
        )
        writer.writeheader()
        for row in sorted(coverage_rows, key=lambda item: (-int(item["channels_with_epg"]), item["output_group"])):
            writer.writerow(row)

    index_path = epg_dir / "index.json"
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    readme_path = epg_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "Bu klasor ulke bazli EPG giris dosyalarini icerir.",
                "",
                "Dosyalar:",
                "- `channels/*.xml`: `iptv-org/epg` icin custom channels.xml dosyalari.",
                "- `coverage.csv`: her ulkedeki EPG kapsama ozeti.",
                "- `index.json`: dosya yollarini makine tarafinda kullanmak icin indeks.",
                "",
                "Bu ortamda Docker/Node bulunmadigi icin gercek `guide.xml` dosyalari otomatik uretilmedi.",
                "Docker veya Node kurulduktan sonra resmi `iptv-org/epg` araciyla `channels/*.xml` girdilerini kullanarak",
                "her ulke icin XMLTV dosyasi uretebilir ve daha sonra oynaticida bu dosyalari EPG olarak tanitabilirsiniz.",
                "",
                "Onerilen akis:",
                "1. `channels/Turkey.xml` gibi bir dosya secin.",
                "2. `iptv-org/epg` ile bu dosyadan `Turkey.xml` guide dosyasi uretin.",
                "3. Eger guide dosyalarini bir HTTP sunucusunda yayinlarsaniz scripti `--epg-base-url` ile tekrar calistirip",
                "   playlist basligina otomatik `x-tvg-url` ekleyebilirsiniz.",
                "",
                "Ornek:",
                "```powershell",
                "python .\\vavoo_categorizer.py --epg-base-url http://127.0.0.1:8787/epg",
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_review_files(records: list[dict], overrides_dir: Path) -> None:
    overrides_dir.mkdir(parents=True, exist_ok=True)
    review_columns = [
        "source_group",
        "clean_name",
        "occurrences",
        "sample_raw_name",
        "suggested_category",
        "suggested_country_code",
        "suggested_country_name",
        "suggested_logo_url",
        "match_reason",
        "match_score",
        "matched_id",
        "matched_name",
        "matched_country",
        "matched_country_name",
        "matched_categories",
        "matched_website",
        "override_category",
        "override_country_code",
        "override_logo_url",
        "override_tvg_id",
        "override_matched_name",
        "override_matched_country",
        "override_website",
        "notes",
    ]
    needs_review = [
        record
        for record in records
        if record["manual_override"] == "1"
        or not record["logo_url"]
        or record["match_reason"] == ""
        or record["category_source"] in {"default", "keyword", "tag"}
    ]
    by_group: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for record in needs_review:
        bucket = by_group[record["source_group"]]
        key = manual_key(record["clean_name"], record["source_group"])
        current = bucket.get(key)
        if current is None:
            bucket[key] = {
                "source_group": record["source_group"],
                "clean_name": key,
                "occurrences": "1",
                "sample_raw_name": record["raw_name"],
                "suggested_category": record["category"],
                "suggested_country_code": record["resolved_country_code"],
                "suggested_country_name": record["resolved_country_name"],
                "suggested_logo_url": record["logo_url"],
                "match_reason": record["match_reason"],
                "match_score": record["match_score"],
                "matched_id": record["matched_id"],
                "matched_name": record["matched_name"],
                "matched_country": record["matched_country"],
                "matched_country_name": record["matched_country_name"],
                "matched_categories": record["matched_categories"],
                "matched_website": record["matched_website"],
                "override_category": "",
                "override_country_code": "",
                "override_logo_url": "",
                "override_tvg_id": "",
                "override_matched_name": "",
                "override_matched_country": "",
                "override_website": "",
                "notes": "",
            }
        else:
            current["occurrences"] = str(int(current["occurrences"]) + 1)

    for source_group, rows in by_group.items():
        file_path = overrides_dir / f"{safe_file_fragment(source_group)}.csv"
        existing_overrides: dict[str, dict[str, str]] = {}
        if file_path.exists():
            with file_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    clean_name = (row.get("clean_name") or "").strip()
                    if clean_name:
                        existing_overrides[clean_name] = row

        ordered_rows = sorted(
            rows.values(),
            key=lambda row: (-int(row["occurrences"]), normalize_name(row["clean_name"])),
        )
        with file_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=review_columns)
            writer.writeheader()
            for row in ordered_rows:
                existing = existing_overrides.get(row["clean_name"], {})
                for field in review_columns:
                    if field.startswith("override_") or field == "notes":
                        row[field] = (existing.get(field) or row[field]).strip()
                writer.writerow(row)


def write_reports(records: list[dict], report_dir: Path, category_meta: list[dict]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    rows_path = report_dir / "channel_report.csv"
    with rows_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_group",
                "raw_name",
                "clean_name",
                "category",
                "category_source",
                "match_reason",
                "match_score",
                "matched_id",
                "matched_name",
                "matched_country",
                "matched_country_name",
                "matched_categories",
                "matched_website",
                "epg_guides_count",
                "resolved_country_code",
                "resolved_country_name",
                "output_group",
                "logo_url",
                "manual_override",
                "manual_notes",
                "url",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(record)

    unresolved_path = report_dir / "unresolved_channels.csv"
    unresolved = [
        record
        for record in records
        if record["match_reason"] == "" or record["category_source"] in {"default", "keyword", "tag"} or not record["logo_url"]
    ]
    with unresolved_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_group",
                "raw_name",
                "clean_name",
                "category",
                "category_source",
                "resolved_country_code",
                "resolved_country_name",
                "epg_guides_count",
                "logo_url",
                "url",
            ],
        )
        writer.writeheader()
        for record in unresolved:
            writer.writerow(
                {
                    "source_group": record["source_group"],
                    "raw_name": record["raw_name"],
                    "clean_name": record["clean_name"],
                    "category": record["category"],
                    "category_source": record["category_source"],
                    "resolved_country_code": record["resolved_country_code"],
                    "resolved_country_name": record["resolved_country_name"],
                    "epg_guides_count": record["epg_guides_count"],
                    "logo_url": record["logo_url"],
                    "url": record["url"],
                }
            )

    summary = {
        "total_entries": len(records),
        "source_groups": {},
        "output_groups": {},
        "categories": Counter(record["category"] for record in records),
        "match_methods": Counter(record["match_reason"] or "unmatched" for record in records),
        "category_methods": Counter(record["category_source"] for record in records),
        "logos": {
            "with_logo": sum(1 for record in records if record["logo_url"]),
            "without_logo": sum(1 for record in records if not record["logo_url"]),
        },
        "epg": {
            "with_tvg_id": sum(1 for record in records if record["matched_id"]),
            "with_epg_guides": sum(1 for record in records if int(record.get("epg_guides_count", "0") or "0") > 0),
            "without_epg_guides": sum(1 for record in records if int(record.get("epg_guides_count", "0") or "0") == 0),
        },
        "manual_overrides": sum(1 for record in records if record["manual_override"] == "1"),
        "category_reference": category_meta,
    }

    group_buckets: dict[str, dict[str, object]] = {}
    for source_group in sorted({record["source_group"] for record in records}):
        bucket_records = [record for record in records if record["source_group"] == source_group]
        group_buckets[source_group] = {
            "entries": len(bucket_records),
            "categories": Counter(record["category"] for record in bucket_records),
            "matched": sum(1 for record in bucket_records if record["match_reason"]),
            "epg_guides": sum(1 for record in bucket_records if int(record.get("epg_guides_count", "0") or "0") > 0),
        }
    summary["source_groups"] = group_buckets

    output_buckets: dict[str, dict[str, object]] = {}
    for output_group in sorted({record["output_group"] for record in records}):
        bucket_records = [record for record in records if record["output_group"] == output_group]
        output_buckets[output_group] = {
            "entries": len(bucket_records),
            "categories": Counter(record["category"] for record in bucket_records),
            "epg_guides": sum(1 for record in bucket_records if int(record.get("epg_guides_count", "0") or "0") > 0),
        }
    summary["output_groups"] = output_buckets

    summary_path = report_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def categorize_playlist(
    input_path: Path,
    output_dir: Path,
    report_dir: Path,
    overrides_dir: Path,
    epg_dir: Path,
    epg_base_url: str | None,
    epg_existing_dir: Path | None,
    refresh_db: bool,
) -> dict[str, int]:
    categories_meta = load_remote_json(
        IPTV_ORG_CATEGORIES_URL,
        CACHE_DIR / "iptv-org-categories.json",
        refresh=refresh_db,
    )
    countries_meta = load_remote_json(
        IPTV_ORG_COUNTRIES_URL,
        CACHE_DIR / "iptv-org-countries.json",
        refresh=refresh_db,
    )
    channel_payload = load_remote_json(
        IPTV_ORG_CHANNELS_URL,
        CACHE_DIR / "iptv-org-channels.json",
        refresh=refresh_db,
    )
    guides_payload = load_remote_json(
        IPTV_ORG_GUIDES_URL,
        CACHE_DIR / "iptv-org-guides.json",
        refresh=refresh_db,
    )
    logos_payload = load_remote_json(
        IPTV_ORG_LOGOS_URL,
        CACHE_DIR / "iptv-org-logos.json",
        refresh=refresh_db,
    )

    country_names = build_country_names(countries_meta)
    logo_index = build_logo_index(logos_payload)
    guide_index = build_guide_index(guides_payload)
    entries = parse_m3u(input_path)
    db_channels, exact_index, token_index = build_db_channels(channel_payload, logo_index)
    channels_by_id = {channel.channel_id: channel for channel in db_channels if channel.channel_id}
    manual_overrides = load_manual_overrides(overrides_dir)

    rows = []
    classification_cache: dict[tuple[str, str, tuple[str, ...]], dict[str, str]] = {}
    for entry in entries:
        cache_key = (entry.source_group, entry.clean_name, entry.tags)
        cached = classification_cache.get(cache_key)
        if cached is None:
            allow_fuzzy = keyword_category_hint(entry.clean_name) is None and tag_category_hint(entry.tags) is None
            match = find_best_match(
                entry,
                db_channels,
                exact_index,
                token_index,
                allow_fuzzy=allow_fuzzy,
            )
            category, category_source = resolve_category(entry, match)
            resolved_country_code, resolved_country_name = resolve_country_info(entry, match, country_names)
            cached = {
                "category": category,
                "category_source": category_source,
                "match_reason": match.reason or "",
                "match_score": f"{match.score:.3f}" if match.channel else "",
                "matched_id": match.channel.channel_id if match.channel else "",
                "matched_name": match.channel.name if match.channel else "",
                "matched_country": match.channel.country if match.channel else "",
                "matched_country_name": (
                    country_names.get(match.channel.country, match.channel.country)
                    if match.channel and match.channel.country
                    else ""
                ),
                "matched_categories": ",".join(match.channel.categories) if match.channel else "",
                "matched_website": match.channel.website or "" if match.channel else "",
                "resolved_country_code": resolved_country_code,
                "resolved_country_name": resolved_country_name,
                "output_group": resolved_country_name or entry.source_group,
                "logo_url": match.channel.logo_url or "" if match.channel else "",
                "manual_override": "",
                "manual_notes": "",
            }
            classification_cache[cache_key] = cached

        row = apply_manual_override(
            {
                "source_group": entry.source_group,
                "raw_name": entry.raw_name,
                "clean_name": entry.clean_name,
                "category": cached["category"],
                "category_source": cached["category_source"],
                "match_reason": cached["match_reason"],
                "match_score": cached["match_score"],
                "matched_id": cached["matched_id"],
                "matched_name": cached["matched_name"],
                "matched_country": cached["matched_country"],
                "matched_country_name": cached["matched_country_name"],
                "matched_categories": cached["matched_categories"],
                "matched_website": cached["matched_website"],
                "resolved_country_code": cached["resolved_country_code"],
                "resolved_country_name": cached["resolved_country_name"],
                "output_group": cached["output_group"],
                "logo_url": cached["logo_url"],
                "manual_override": cached["manual_override"],
                "manual_notes": cached["manual_notes"],
                "epg_guides_count": "0",
                "url": entry.url,
            },
            manual_overrides.get((entry.source_group, manual_key(entry.clean_name, entry.source_group))),
            country_names,
            logo_index,
            channels_by_id,
        )
        row["epg_guides_count"] = str(len(guide_index.get(row["matched_id"], []))) if row["matched_id"] else "0"
        rows.append(row)

    write_epg_files(rows, epg_dir, guide_index)
    epg_url_map = build_epg_url_map(rows, epg_base_url, existing_epg_dir=epg_existing_dir)
    write_m3u8_files(rows, output_dir, epg_url_map=epg_url_map)
    write_reports(rows, report_dir, categories_meta)
    write_review_files(rows, overrides_dir)

    return {
        "entries": len(rows),
        "groups": len({row["output_group"] for row in rows}),
        "matched": sum(1 for row in rows if row["match_reason"]),
        "manual": sum(1 for row in rows if row["manual_override"] == "1"),
        "logos": sum(1 for row in rows if row["logo_url"]),
        "epg": sum(1 for row in rows if int(row.get("epg_guides_count", "0") or "0") > 0),
        "keyword_or_default": sum(1 for row in rows if row["category_source"] in {"keyword", "default", "tag"}),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split a Vavoo M3U file into source-group M3U8 files and categorize channels."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input M3U playlist path.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output M3U8 directory.")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR, help="Report directory.")
    parser.add_argument("--epg-dir", type=Path, default=DEFAULT_EPG_DIR, help="EPG helper output directory.")
    parser.add_argument(
        "--epg-existing-dir",
        type=Path,
        default=None,
        help="Only write x-tvg-url for countries whose XML already exists in this directory.",
    )
    parser.add_argument(
        "--overrides-dir",
        type=Path,
        default=DEFAULT_OVERRIDE_DIR,
        help="Country-by-country manual review and override CSV directory.",
    )
    parser.add_argument(
        "--epg-base-url",
        default="",
        help="If set, writes x-tvg-url headers pointing to <base>/<country>.xml.",
    )
    parser.add_argument("--refresh-db", action="store_true", help="Refresh cached IPTV Org data.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    stats = categorize_playlist(
        args.input,
        args.output_dir,
        args.report_dir,
        args.overrides_dir,
        args.epg_dir,
        args.epg_base_url or None,
        args.epg_existing_dir,
        args.refresh_db,
    )
    print(
        "Created {groups} country files from {entries} entries. IPTV Org/manual matched {matched} entries; "
        "{logos} entries now have logos, {epg} entries have EPG guide mappings, {manual} entries use manual overrides, and "
        "{keyword_or_default} entries still use keyword/tag/default category fallback.".format(**stats)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
