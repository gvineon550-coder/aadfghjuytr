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


# 📌 Расширенная нормализация: убирает всё, что мешает сопоставлению
COUNTRY_PREFIX = re.compile(r'^(ru|russia|россия|рф|ua|ukraine|by|belarus|kz|kazakhstan)[\s:\-|]+', re.IGNORECASE)
QUALITY_SUFFIX = re.compile(r'\b(hd|sd|fhd|fullhd|uhd|4k|8k|2160p|1080p|720p|576p|480p|360p|hevc|h\.?264|h\.?265)\b', re.IGNORECASE)
NOISE_WORDS    = re.compile(r'\b(тв|tv|телеканал|channel|прямой\s+эфир|live|international|int|global|europa|europe|cis|снг|mir|мир)\b', re.IGNORECASE)
PUNCTUATION    = re.compile(r'[\(\)\[\]\{\}\"\'«»“”`]')


def normalize_name(name: str) -> str:
    """Максимальная очистка названия для поиска в EPG."""
    if not name:
        return ""
    name = COUNTRY_PREFIX.sub('', name)
    name = PUNCTUATION.sub('', name)
    name = QUALITY_SUFFIX.sub('', name)
    name = NOISE_WORDS.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name


def load_logos(path: str) -> dict:
    log(f"📥 Загружаем логотипы из {path}...")
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


def build_epg_mapping(url: str) -> tuple[dict, dict]:
    """Возвращает (точная_карта, карта_для_нечёткого_поиска)."""
    log(f"📥 Скачиваем EPG из {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    log(f"✅ Скачано {len(raw)} байт")

    # 🚨 ИСПРАВЛЕНИЕ: не распаковываем в память, а читаем gzip на лету
    if raw[:2] == b"\x1f\x8b":
        log("📦 Файл сжат gzip — распаковываем на лету (экономия памяти)...")
        source = gzip.GzipFile(fileobj=io.BytesIO(raw))
    else:
        log("📦 Файл без сжатия — читаем как есть...")
        source = io.BytesIO(raw)

    log("🔍 Парсим XMLTV (потоково)...")
    exact_map = {}
    fuzzy_map = defaultdict(set)

    try:
        context = ET.iterparse(source, events=("end",))
        for event, elem in context:
            if elem.tag == "channel":
                epg_id = elem.get("id")
                if epg_id:
                    for name_node in elem.findall("display-name"):
                        if name_node.text:
                            norm_name = normalize_name(name_node.text)
                            if norm_name:
                                exact_map[norm_name] = epg_id
                                for word in norm_name.split():
                                    if len(word) > 2:
                                        fuzzy_map[word].add(epg_id)
                elem.clear()
    except Exception as e:
        log(f"❌ Ошибка парсинга XML: {e}")
        raise

    log(f"✅ Загружено {len(exact_map)} уникальных названий (точных) и {len(fuzzy_map)} ключевых слов (для поиска)")
    return exact_map, fuzzy_map


def find_epg_id(channel_name: str, exact_map: dict, fuzzy_map: dict) -> str | None:
    """Ищет EPG ID сначала точно, затем по вхождению ключевых слов."""
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


def enrich(src_path: str, out_path: str, logos: dict, exact_map: dict, fuzzy_map: dict) -> None:
    log(f"📖 Читаем {src_path} ...")
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    log(f"✅ Прочитано {len(lines)} строк")

    out = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    total_channels = 0
    matched_epg = 0
    matched_logo = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#EXTM3U"):
            continue

        if stripped.startswith("#EXTINF"):
            total_channels += 1
            parts = line.rsplit(",", 1)
            channel_name = parts[1].strip() if len(parts) > 1 else ""

            epg_id = find_epg_id(channel_name, exact_map, fuzzy_map)
            if epg_id:
                matched_epg += 1
                if 'tvg-id="' in line:
                    line = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{epg_id}"', line, count=1)
                else:
                    line = line.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-id="{epg_id}"', 1)
            else:
                log(f"⚠️  Нет EPG для: '{channel_name}'")

            if 'tvg-name="' not in line:
                line = re.sub(r'(tvg-id="[^"]*")', rf'\1 tvg-name="{channel_name}"', line, count=1)

            m = re.search(r'tvg-id="([^"]*)"', line)
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

    log(f"📊 ИТОГО:")
    log(f"   Всего каналов:      {total_channels}")
    log(f"   Сопоставлено EPG:   {matched_epg}  ({matched_epg*100//max(total_channels,1)}%)")
    log(f"   Сопоставлено лого:  {matched_logo} ({matched_logo*100//max(total_channels,1)}%)")

    if matched_epg == 0:
        log("🚨 ВНИМАНИЕ: ни один канал не сопоставлен с EPG!")
    elif matched_epg < total_channels * 0.5:
        log(f"⚠️  Сопоставлено меньше 50% каналов — проверьте названия в логе.")

    log(f"💾 Пишем {out_path} ...")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    log(f"✅ Записано {len(out)} строк в {out_path}")


def main() -> None:
    log("🚀 СТАРТ обогащения плейлиста")
    logos = load_logos(LOGOS_API)
    exact_map, fuzzy_map = build_epg_mapping(EPG_URL)
    enrich(SOURCE, OUTPUT, logos, exact_map, fuzzy_map)
    log("🎉 ГОТОВО")


if __name__ == "__main__":
    main()
