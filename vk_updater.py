import json
import os
import sys
import uuid

import yt_dlp
import requests

CONFIG = "vk_config.json"
OUTPUT = "vk_live.m3u"
NETLIFY = "https://incomparable-hamster-974986.netlify.app/vk-stream/"


def get_category_channels(cat_id):
    url = (f"https://api.live.vkvideo.ru/v1/catalog/"
           f"public_video_streams/category/{cat_id}/stream/?limit=100")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://live.vkvideo.ru",
        "Referer": "https://live.vkvideo.ru/",
        "X-App": "streams_web",
        "X-From-Id": str(uuid.uuid4()),
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        blogs = r.json().get("data", {}).get("streamBlogs", [])
        result = []
        for s in blogs:
            b = s.get("blog", {})
            if not b.get("blogUrl"):
                continue
            name = (b.get("title") or b.get("owner", {}).get("displayName")
                    or b["blogUrl"])
            logo = b.get("owner", {}).get("avatarUrl") or b.get("coverUrl") or ""
            result.append({
                "name": name.replace(",", " ").strip()[:60],
                "blog_url": b["blogUrl"],
                "logo": logo,
            })
        return result
    except Exception as e:
        print(f"API error {cat_id}: {e}")
        return []


def resolve_manual(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/120.0.0.0 Safari/537.36"}
    opts = {
        'quiet': True, 'no_warnings': True,
        'format': 'best[protocol^=m3u8]/best',
        'skip_download': True,
        'http_headers': headers,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = None
            for f in info.get('formats', []):
                if f.get('protocol') == 'm3u8' and f.get('url'):
                    stream_url = f['url']
                    break
            if not stream_url:
                stream_url = info.get('url')
            if stream_url:
                return {"url": stream_url,
                        "title": info.get('title') or "",
                        "thumbnail": info.get('thumbnail') or ""}
    except Exception:
        pass
    return None


def main():
    if not os.path.exists(CONFIG):
        print(f"{CONFIG} not found")
        sys.exit(1)

    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    lines = ["#EXTM3U"]

    # 1. VK Live категории → ссылки на Netlify
    for cat in cfg.get("categories", []):
        channels = get_category_channels(cat)
        print(f"Category {cat}: {len(channels)} channels")
        for ch in channels:
            lines.append(
                f'#EXTINF:-1 tvg-logo="{ch["logo"]}" '
                f'group-title="📺 VK Live",{ch["name"]}'
            )
            lines.append(f'{NETLIFY}{ch["blog_url"]}')

    # 2. Ручные VK Video
    for ch in cfg.get("channels", []):
        info = resolve_manual(ch["url"])
        if info:
            name = (info.get("title") or ch["name"]).replace(",", " ").strip()[:60]
            logo = ch.get("logo") or info.get("thumbnail") or ""
            group = ch.get("group") or "🎬 VK Video"
            lines.append(
                f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}'
            )
            lines.append(
                '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; '
                'Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
            lines.append('#EXTVLCOPT:http-referrer=https://vk.com/')
            lines.append('#EXTVLCOPT:http-origin=https://vk.com')
            lines.append(info["url"])
            print(f"Manual: {name} OK")
        else:
            print(f"Manual: {ch['name']} FAILED")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    total = sum(1 for l in lines if l.startswith("#EXTINF"))
    print(f"Total: {total} channels")


if __name__ == "__main__":
    main()
