import json
import yt_dlp
import requests
import os
import sys
import time
import uuid

CONFIG_FILE = "vk_config.json"
CACHE_FILE = "rutube_cache.json"
OUTPUT_FILE = "vk_live.m3u"

# 🎨 Цвета для логов
C_GREEN = '\033[92m'
C_RED = '\033[91m'
C_YELLOW = '\033[93m'
C_CYAN = '\033[96m'
C_BOLD = '\033[1m'
C_RESET = '\033[0m'

class Progress:
    def __init__(self, total):
        self.total = total
        self.done = 0
        self.success = 0
        self.failed = 0

    def update(self, success, name=""):
        self.done += 1
        if success: self.success += 1
        else: self.failed += 1
        self.render(success, name)

    def render(self, success, name):
        pct = int((self.done / self.total) * 100) if self.total > 0 else 100
        bar_len = 30
        filled = int(bar_len * self.done / self.total) if self.total > 0 else bar_len
        bar = "█" * filled + "░" * (bar_len - filled)
        status_icon = f"{C_GREEN}✅{C_RESET}" if success else f"{C_RED}❌{C_RESET}"
        short_name = (name[:25] + '..') if len(name) > 25 else name
        sys.stdout.write(f"\r{C_CYAN}[{bar}]{C_RESET} {pct}% ({self.done}/{self.total}) | {C_GREEN}Успех: {self.success}{C_RESET} | {C_RED}Офлайн: {self.failed}{C_RESET} | {status_icon} {short_name:<25}")
        sys.stdout.flush()

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_streams_from_category(category_id):
    url = f"https://api.live.vkvideo.ru/v1/catalog/public_video_streams/category/{category_id}/stream/?limit=100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://live.vkvideo.ru",
        "Referer": "https://live.vkvideo.ru/",
        "X-App": "streams_web",
        "X-From-Id": str(uuid.uuid4()),
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        streams = data.get("data", {}).get("streamBlogs", [])
        result = []
        for s in streams:
            blog = s.get("blog", {})
            blog_url = blog.get("blogUrl")
            if not blog_url: continue
            raw_name = blog.get("title") or blog.get("owner", {}).get("displayName") or blog_url
            name = raw_name[:40] + "..." if len(raw_name) > 40 else raw_name
            name = name.replace(",", " ")
            channel_url = f"https://live.vkvideo.ru/{blog_url}"
            logo = blog.get("owner", {}).get("avatarUrl") or blog.get("coverUrl") or ""
            result.append({"name": name, "url": channel_url, "logo": logo, "group": "📺 VK Live"})
        return result
    except Exception as e:
        print(f"\n{C_RED}Ошибка API VK категории {category_id}: {e}{C_RESET}")
        return []

def get_stream_info(vk_url):
    is_rutube = "rutube.ru" in vk_url
    is_vk = "vk.com" in vk_url or "vkvideo.ru" in vk_url
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    if is_rutube:
        headers['Referer'] = 'https://rutube.ru/'
        headers['Origin'] = 'https://rutube.ru'
    elif is_vk:
        headers['Referer'] = 'https://vk.com/'
        
    ydl_opts = {
        'quiet': True, 'no_warnings': True,
        'format': 'best[protocol^=m3u8]/best',
        'skip_download': True,
        'http_headers': headers
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(vk_url, download=False)
            stream_url = None
            for fmt in info.get('formats', []):
                if fmt.get('protocol') == 'm3u8' and fmt.get('url'):
                    stream_url = fmt['url']
                    break
            if not stream_url: stream_url = info.get('url')
            if not stream_url: return None
                
            return {
                "url": stream_url,
                "title": info.get('title') or "",
                "thumbnail": info.get('thumbnail') or ""
            }
    except Exception:
        return None

def main():
    print(f"{C_CYAN}{C_BOLD}=== VK & Rutube (Smart Groups & Full Cache) ==={C_RESET}")
    if not os.path.exists(CONFIG_FILE):
        print(f"{C_RED}Файл vk_config.json не найден!{C_RESET}")
        return
        
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    rutube_cache = load_cache()
    all_channels = []
    
    # 1. VK Live (по категориям)
    for cat_id in config.get("categories", []):
        print(f"{C_CYAN}[*] Загрузка VK категории: {cat_id}{C_RESET}")
        all_channels.extend(get_streams_from_category(cat_id))
        
    # 2. Ручные каналы
    for ch in config.get("channels", []):
        if "group" not in ch or not ch["group"]:
            url = ch['url']
            if "rutube.ru" in url: ch["group"] = "📼 Rutube"
            elif "vk.com" in url or "vkvideo.ru" in url: ch["group"] = "🎬 VK Video"
            else: ch["group"] = "📦 Разное"
        all_channels.append(ch)

    if not all_channels:
        print(f"{C_YELLOW}[!] Каналы не найдены.{C_RESET}")
        return

    print(f"\n{C_CYAN}[*] Всего каналов: {len(all_channels)}. Начинаем проверку...{C_RESET}\n")
    
    lines = ["#EXTM3U"]
    progress = Progress(len(all_channels))
    
    for ch in all_channels:
        url = ch['url']
        info = None
        
        # 🧠 Кэш для ВСЕХ ссылок Rutube
        is_rutube = "rutube.ru" in url
        
        if is_rutube and url in rutube_cache:
            info = rutube_cache[url]
        else:
            info = get_stream_info(url)
            if info and is_rutube:
                rutube_cache[url] = info  # Сохраняем в кэш
        
        if info:
            final_logo = ch.get("logo") or info.get("thumbnail") or ""
            final_name = ch["name"]
            
            if final_name.startswith("Rutube") or final_name.startswith("Эфир"):
                final_name = info.get("title") or final_name
            
            final_name = final_name[:60].replace(",", " ")
            group_name = ch.get("group", "📦 Разное")

            logo_attr = f' tvg-logo="{final_logo}"' if final_logo else ""
            lines.append(f'#EXTINF:-1{logo_attr} group-title="{group_name}",{final_name}')
            
            # Стелс для плеера
            lines.append("#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            if "rutube.ru" in url:
                lines.append("#EXTVLCOPT:http-referrer=https://rutube.ru/")
                lines.append("#EXTVLCOPT:http-origin=https://rutube.ru")
            elif "vk.com" in url or "vkvideo.ru" in url:
                lines.append("#EXTVLCOPT:http-referrer=https://vk.com/")
                lines.append("#EXTVLCOPT:http-origin=https://vk.com")
                
            lines.append(info["url"])
            progress.update(True, final_name)
        else:
            progress.update(False, ch["name"])
            
    print("\n")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")
        
    save_cache(rutube_cache)
    
    groups = {}
    for line in lines:
        if "group-title=" in line:
            g = line.split('group-title="')[1].split('"')[0]
            groups[g] = groups.get(g, 0) + 1
            
    print(f"{C_GREEN}{C_BOLD}✅ Готово! Успешно добавлено: {progress.success} из {len(all_channels)}{C_RESET}")
    for g, count in groups.items():
        print(f"  {g}: {count} каналов")

if __name__ == "__main__":
    main()
