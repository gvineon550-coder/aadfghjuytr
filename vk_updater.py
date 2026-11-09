import json
import os
import uuid
import time

import requests
import yt_dlp

CONFIG = "vk_config.json"
OUTPUT = "vk_live.m3u"
OUTPUT_TOP = "vk_top.m3u"
NETLIFY = "https://incomparable-hamster-974986.netlify.app/vk-stream/"


def get_category_channels(cat_id):
    """Возвращает список каналов с метаданными: зрители, категория, isOnline."""
    url = (
        f"https://api.live.vkvideo.ru/v1/catalog/"
        f"public_video_streams/category/{cat_id}/stream/?limit=100"
    )
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
            name = (
                b.get("title")
                or b.get("owner", {}).get("displayName")
                or b["blogUrl"]
            )
            logo = (
                b.get("owner", {}).get("avatarUrl")
                or b.get("coverUrl")
                or ""
            )
            category = s.get("category", {}).get("title") or "📺 VK Live"
            viewers = s.get("count", {}).get("viewers", 0)
            is_online = s.get("isOnline", False)
            result.append({
                "name": name.replace(",", " ").strip()[:60],
                "blog_url": b["blogUrl"],
                "logo": logo,
                "category": category,
                "viewers": viewers,
                "is_online": is_online,
            })
        return result
    except Exception as e:
        print(f"API error {cat_id}: {e}")
        return []


def resolve_manual(url):
    """Ручные каналы VK Video — парсим через yt-dlp."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36'
    }
    opts = {
        'quiet': True,
        'no_warnings': True,
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
                return {
                    "url": stream_url,
                    "title": info.get('title') or "",
                    "thumbnail": info.get('thumbnail') or "",
                }
    except Exception:
        pass
    return None


def build_playlist(channels, include_viewers=False):
    """Формирует m3u-плейлист из списка каналов."""
    lines = ["#EXTM3U"]
    for ch in channels:
        name = ch["name"]
        # 🔴 LIVE-префикс для активных
        if ch.get("is_online"):
            name = f"🔴 {name}"
        # 👁 Зрители в названии
        if include_viewers and ch.get("viewers", 0) > 0:
            name = f"{name} [👁 {ch['viewers']}]"
        
        group = ch.get("category", "📺 VK Live")
        logo = ch.get("logo", "")
        
        lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}'
        )
        lines.append(f'{NETLIFY}{ch["blog_url"]}?v={int(time.time())}')
    return lines


def main():
    if not os.path.exists(CONFIG):
        print(f"{CONFIG} not found")
        return

    with open(CONFIG, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    all_channels = []

    # 1. VK Live категории
    for cat in cfg.get("categories", []):
        channels = get_category_channels(cat)
        online = [c for c in channels if c["is_online"]]
        print(f"Category {cat}: {len(channels)} total, {len(online)} online")
        all_channels.extend(online)  # только онлайн

    # 2. Ручные VK Video каналы
    manual_lines = []
    for ch in cfg.get("channels", []):
        info = resolve_manual(ch["url"])
        if info:
            name = (info.get("title") or ch["name"]).replace(",", " ").strip()[:60]
            logo = ch.get("logo") or info.get("thumbnail") or ""
            group = ch.get("group") or "🎬 VK Video"
            manual_lines.append(
                f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}'
            )
            manual_lines.append(
                '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; '
                'Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
            manual_lines.append('#EXTVLCOPT:http-referrer=https://vk.com/')
            manual_lines.append('#EXTVLCOPT:http-origin=https://vk.com')
            manual_lines.append(info["url"])
            print(f"Manual: {name} OK")
        else:
            print(f"Manual: {ch['name']} FAILED")

    # 3. Сортировка по зрителям (популярные вверху)
    all_channels.sort(key=lambda c: -c.get("viewers", 0))

    # 4. Полный плейлист (с зрителями)
    full = build_playlist(all_channels, include_viewers=True)
    full += manual_lines
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write("\n".join(full) + "\n")

    # 5. Топ-20 (без зрителей, для чистоты)
    top = build_playlist(all_channels[:20], include_viewers=False)
    with open(OUTPUT_TOP, 'w', encoding='utf-8') as f:
        f.write("\n".join(top) + "\n")

    print(f"Full playlist: {len(all_channels)} channels + {len(manual_lines)//5} manual")
    print(f"Top playlist: {min(20, len(all_channels))} channels")


if __name__ == "__main__":
    main()
