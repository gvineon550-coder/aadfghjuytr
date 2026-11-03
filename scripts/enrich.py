#!/usr/bin/env python3
import json
import re

SOURCE       = "source_ru.m3u"
CHANNELS_API = "channels.json"
LOGOS_API    = "logos.json"
OUTPUT       = "wink_ru.m3u"
UA           = "WINK/1.44.1 (AndroidTV/9) HlsWinkPlayer"

def load_logos(path: str) -> dict:
    """Загружает логотипы из logos.json (связь по channel_id)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    
    logos = {}
    for item in data:
        cid = (item.get("channel") or "").strip()
        logo = (item.get("url") or "").strip()
        if cid and logo.startswith(("http://", "https://")):
            # Если для канала несколько логотипов, берем первый попавшийся
            if cid not in logos:
                logos[cid] = logo
    return logos

def enrich(src_path: str, out_path: str, logos: dict) -> None:
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    
    out = []
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith("#EXTINF"):
            # 1. Добавляем логотип
            m = re.search(r'tvg-id="([^"]*)"', line)
            if m:
                base_id = m.group(1).split("@", 1)[0]
                logo = logos.get(base_id)
                if logo:
                    if 'tvg-logo="' in line:
                        line = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo}"', line, count=1)
                    else:
                        line = re.sub(r'(tvg-id="[^"]*")', rf'\1 tvg-logo="{logo}"', line, count=1)
            out.append(line)
            
            # 2. Добавляем User-Agent
            out.append(f"#EXTVLCOPT:http-user-agent={UA}")
            
        elif stripped.startswith("#EXTVLCOPT"):
            # Удаляем старые UA, чтобы не было дублей
            if "http-user-agent" in stripped.lower():
                continue
            out.append(line)
        else:
            out.append(line)
            
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

def main() -> None:
    logos = load_logos(LOGOS_API)
    enrich(SOURCE, OUTPUT, logos)

if __name__ == "__main__":
    main()
