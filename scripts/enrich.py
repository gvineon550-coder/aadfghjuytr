#!/usr/bin/env python3
import json
import re
import gzip
import io
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

SOURCE       = "source_ru.m3u"
CHANNELS_API = "channels.json"
LOGOS_API    = "logos.json"
EPG_URL      = "https://iptvx.one/epg/epg_lite.xml.gz"
OUTPUT       = "wink_ru.m3u"
UA           = "WINK/1.44.1 (AndroidTV/9) HlsWinkPlayer"


def log(msg: str) -> None:
    print(msg, flush=True)


def progress_bar(percent: int, length: int = 20) -> str:
    """Рисует текстовый прогресс-бар."""
    filled = int(length * percent / 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}]"


# 📌 Нормализация для поиска по имени
COUNTRY_PREFIX = re.compile(r'^(ru|russia|россия|рф|ua|ukraine|by|belarus|kz|kazakhstan)[\s:\-|]+', re.IGNORECASE)
QUALITY_SUFFIX = re.compile(r'\b(hd|sd|fhd|fullhd|uhd|4k|8k|2160p|1080p|720p|576p|480p|360p|hevc|h\.?264|h\.?265)\b', re.IGNORECASE)
NOISE_WORDS    = re.compile(r'\b(тв|tv|телеканал|channel|прямой\s+эфир|live|international|int|global|europa|europe|cis|снг|mir|мир)\b', re.IGNORECASE)
PUNCTUATION    = re.compile(r'[\(\)\[\]\{\}\"\'«»“”`]')


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = COUNTRY_PREFIX.sub('', name)
    name = PUNCTUATION.sub('', name)
    name = QUALITY_SUFFIX.sub('', name)
    name = NOISE_WORDS.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name


def load_logos(path: str) -> dict:
    log(f"📥 Загружаем логотипы...")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logos = {}
    for item in data:
        cid = (item.get("channel") or "").strip()
        logo = (item.get("url") or "").strip()
        if cid and logo.startswith(("http://", "https://")):
            if cid not in logos:
                logos[cid] = logo
    log(f"✅ Загружено {len(logos)} логотипов")
    return logos


def build_epg_mapping(url: str) -> tuple[set, dict, dict]:
    log(f"📥 Скачиваем и парсим EPG (это займет около минуты)...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()

    if raw[:2] == b"\x1f\x8b":
        source = gzip.GzipFile(fileobj=io.BytesIO(raw))
    else:
        source = io.BytesIO(raw)

    epg_ids = set()
    exact_map = {}
    fuzzy_map = defaultdict(set)

    context = ET.iterparse(source, events=("end",))
    for event, elem in context:
        if elem.tag == "channel":
            epg_id = elem.get("id")
            if epg_id:
                epg_ids.add(epg_id)
                for name_node in elem.findall("display-name"):
                    if name_node.text:
                        norm_name = normalize_name(name_node.text)
                        if norm_name:
                            exact_map[norm_name] = epg_id
                            for word in norm_name.split():
                                if len(word) > 2:
                                    fuzzy_map[word].add(epg_id)
            elem.clear()

    log(f"✅ EPG загружено: {len(epg_ids)} ID, {len(exact_map)} названий")
    return epg_ids, exact_map, fuzzy_map


def find_epg_id(channel_name: str, exact_map: dict, fuzzy_map: dict) -> str | None:
    norm_name = normalize_name(channel_name)
    if not norm_name:
        return None
    if norm_name in exact_map:
        return exact_map[norm_name]
    words = sorted([w for w in norm_name.split() if len(w) > 2], key=len, reverse=True)
    for word in words:
        candidates = fuzzy_map.get(word)
        if candidates and len(candidates) == 1:
            return list(candidates)[0]
    return None


def enrich(src_path: str, out_path: str, logos: dict, epg_ids: set, exact_map: dict, fuzzy_map: dict) -> None:
    log(f"📖 Читаем плейлист...")
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    out = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    total_channels = 0
    matched_epg_id = 0
    matched_epg_name = 0
    matched_logo = 0
    unmatched_channels = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#EXTM3U"):
            continue

        if stripped.startswith("#EXTINF"):
            total_channels += 1
            parts = line.rsplit(",", 1)
            channel_name = parts[1].strip() if len(parts) > 1 else ""

            # 1. Поиск по ID
            m = re.search(r'tvg-id="([^"]*)"', line)
            epg_id = None
            if m:
                original_id = m.group(1)
                base_id = original_id.split("@", 1)[0]
                if base_id in epg_ids:
                    epg_id = base_id
                    matched_epg_id += 1

            # 2. Поиск по названию
            if not epg_id:
                epg_id = find_epg_id(channel_name, exact_map, fuzzy_map)
                if epg_id:
                    matched_epg_name += 1
                else:
                    unmatched_channels.append(channel_name)

            if epg_id:
                if 'tvg-id="' in line:
                    line = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{epg_id}"', line, count=1)
                else:
                    line = line.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-id="{epg_id}"', 1)

            if 'tvg-name="' not in line:
                line = re.sub(r'(tvg-id="[^"]*")', rf'\1 tvg-name="{channel_name}"', line, count=1)

            if m:
                base_id = m.group(1).split("@", 1)[0]
                logo = logos.get(base_id)
                if logo:
                    matched_logo += 1
                    if 'tvg-logo="' not in line:
                        line = re.sub(r'(tvg-id="[^"]*")', rf'\1 tvg-logo="{logo}"', line, count=1)

            out.append(line)
            out.append(f"#EXTVLCOPT:http-user-agent={UA}")

        elif stripped.startswith("#EXTVLCOPT"):
            if "http-user-agent" in stripped.lower():
                continue
            out.append(line)
        else:
            out.append(line)

    # 📊 КРАСИВАЯ СТАТИСТИКА
    epg_total = matched_epg_id + matched_epg_name
    epg_percent = (epg_total * 100) // max(total_channels, 1)
    logo_percent = (matched_logo * 100) // max(total_channels, 1)

    log("\n" + "━" * 45)
    log("📊 СТАТИСТИКА ОБОГАЩЕНИЯ ПЛЕЙЛИСТА")
    log("━" * 45)
    log(f"Всего каналов:          {total_channels}")
    log("─" * 45)
    log(f"EPG (по ID):            {matched_epg_id}")
    log(f"EPG (по названию):      {matched_epg_name}")
    log(f"EPG (всего):            {epg_total} ({epg_percent}%)  {progress_bar(epg_percent)}")
    log(f"Логотипы:               {matched_logo} ({logo_percent}%)  {progress_bar(logo_percent)}")
    log("━" * 45)

    if unmatched_channels:
        log(f"⚠️  Без EPG осталось {len(unmatched_channels)} каналов. Первые 10:")
        for ch in unmatched_channels[:10]:
            log(f"   - {ch}")
        if len(unmatched_channels) > 10:
            log(f"   ... и еще {len(unmatched_channels) - 10}")
        log("")

    log(f"💾 Пишем {out_path} ...")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    log(f"✅ Успешно записано {len(out)} строк")
    log("🎉 ГОТОВО!\n")


def main() -> None:
    log("🚀 СТАРТ ОБОГАЩЕНИЯ ПЛЕЙЛИСТА")
    logos = load_logos(LOGOS_API)
    epg_ids, exact_map, fuzzy_map = build_epg_mapping(EPG_URL)
    enrich(SOURCE, OUTPUT, logos, epg_ids, exact_map, fuzzy_map)


if __name__ == "__main__":
    main()
