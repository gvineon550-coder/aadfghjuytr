#!/usr/bin/env python3
import json
import re
import sys

SOURCE       = "source_ru.m3u"
CHANNELS_API = "channels.json"
OUTPUT       = "wink_ru.m3u"
UA           = "WINK/1.44.1 (AndroidTV/9) HlsWinkPlayer"

def load_logos(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logos = {}
    for ch in data:
        cid  = (ch.get("id")   or "").strip()
        logo = (ch.get("logo") or "").strip()
        if cid and logo.startswith(("http://", "https://")):
            logos[cid] = logo
    return logos

def enrich(src_path: str, out_path: str, logos: dict) -> None:
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#EXTINF"):
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
            out.append(f"#EXTVLCOPT:http-user-agent={UA}")
        elif stripped.startswith("#EXTVLCOPT"):
            if "http-user-agent" in stripped.lower():
                continue
            out.append(line)
        else:
            out.append(line)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

def main() -> None:
    logos = load_logos(CHANNELS_API)
    enrich(SOURCE, OUTPUT, logos)

if __name__ == "__main__":
    main()
