#!/usr/bin/env python3
import json
import re
import gzip
import urllib.request
import xml.etree.ElementTree as ET

SOURCE       = "source_ru.m3u"
CHANNELS_API = "channels.json"
LOGOS_API    = "logos.json"
EPG_URL      = "https://iptvx.one/epg/epg_lite.xml.gz"
OUTPUT       = "wink_ru.m3u"
UA           = "WINK/1.44.1 (AndroidTV/9) HlsWinkPlayer"

def load_logos(path: str) -> dict:
    """Загружает логотипы из logos.json."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logos = {}
    for item in data:
        cid = (item.get("channel") or "").strip()
        logo = (item.get("url") or "").strip()
        if cid and logo.startswith(("http://", "https://")):
            if cid not in logos:
                logos[cid] = logo
    return logos

def normalize_name(name: str) -> str:
    """Нормализация названия для поиска в EPG."""
    name = name.lower()
    # Убираем кавычки, скобки, лишние пробелы и приведения типа "HD", "SD"
    name = re.sub(r'[\(\)\"\'\[\]]', '', name)
    name = re.sub(r'\b(hd|sd|fullhd|4k|uhd)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def build_epg_mapping(url: str) -> dict:
    """Скачивает EPG, распаковывает и создает карту {нормализованное_имя: epg_id}."""
    print(f"Downloading EPG mapping from {url} ...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    
    # Определяем, сжат ли файл (gzip)
    if raw[:2] == b'\x1f\x8b':
        xml_data = gzip.decompress(raw)
    else:
        xml_data = raw
        
    root = ET.fromstring(xml_data)
    mapping = {}
    
    for channel in root.findall('channel'):
        epg_id = channel.get('id')
        if not epg_id:
            continue
        # Берем все display-name для этого канала
        for name_node in channel.findall('display-name'):
            if name_node.text:
                norm_name = normalize_name(name_node.text)
                mapping[norm_name] = epg_id
                
    print(f"Loaded {len(mapping)} EPG channel names from iptvx.one")
    return mapping

def enrich(src_path: str, out_path: str, logos: dict, epg_mapping: dict) -> None:
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    
    out = []
    # Добавляем ссылку на EPG в заголовок плейлиста
    out.append(f'#EXTM3U x-tvg-url="{EPG_URL}"')
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#EXTM3U'):
            continue  # Пропускаем старый заголовок
            
        if stripped.startswith("#EXTINF"):
            # Извлекаем текущее название канала (текст после последней запятой)
            parts = line.rsplit(',', 1)
            channel_name = parts[1] if len(parts) > 1 else ""
            
            # 1. Пытаемся найти ID в EPG по названию
            norm_name = normalize_name(channel_name)
            epg_id = epg_mapping.get(norm_name)
            
            # 2. Обновляем tvg-id, если нашли совпадение
            if epg_id:
                if 'tvg-id="' in line:
                    line = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{epg_id}"', line, count=1)
                else:
                    line = line.replace('#EXTINF:-1', f'#EXTINF:-1 tvg-id="{epg_id}"', 1)
            
            # 3. Добавляем tvg-name (полезно для плееров, которые ищут по имени)
            if 'tvg-name="' not in line:
                line = re.sub(r'(tvg-id="[^"]*")', rf'\1 tvg-name="{channel_name}"', line, count=1)
            
            # 4. Добавляем логотип (по оригинальному ID из iptv-org)
            m = re.search(r'tvg-id="([^"]*)"', line)
            if m:
                base_id = m.group(1).split("@", 1)[0]
                logo = logos.get(base_id)
                if logo and 'tvg-logo="' not in line:
                    line = re.sub(r'(tvg-id="[^"]*")', rf'\1 tvg-logo="{logo}"', line, count=1)
            
            out.append(line)
            # 5. Добавляем User-Agent Wink
            out.append(f"#EXTVLCOPT:http-user-agent={UA}")
            
        elif stripped.startswith("#EXTVLCOPT"):
            # Удаляем старые User-Agent, чтобы не было дублей
            if "http-user-agent" in stripped.lower():
                continue
            out.append(line)
        else:
            out.append(line)
            
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

def main() -> None:
    logos = load_logos(LOGOS_API)
    epg_mapping = build_epg_mapping(EPG_URL)
    enrich(SOURCE, OUTPUT, logos, epg_mapping)

if __name__ == "__main__":
    main()
