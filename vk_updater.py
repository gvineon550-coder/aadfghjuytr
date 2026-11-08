import json
import yt_dlp
import requests
import os
import sys
import uuid
import re
import urllib3
from urllib.parse import urljoin

# Отключаем предупреждения SSL (как в PyQt-скрипте)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = "vk_config.json"
OUTPUT_FILE = "vk_live.m3u"

# 🎨 Цвета для логов
C_GREEN = '\033[92m'
C_RED = '\033[91m'
C_YELLOW = '\033[93m'
C_CYAN = '\033[96m'
C_BOLD = '\033[1m'
C_RESET = '\033[0m'

# 🕵️ Точные заголовки из PyQt-скрипта
RUTUBE_UA = "Mozilla/5.0 (X11; Linux x86_64)"
RUTUBE_HEADERS = {
    "Accept-Encoding": "gzip, deflate",
    "Accept": "*/*",
    "Connection": "keep-alive",
    "User-Agent": RUTUBE_UA,
}

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

# ==========================================
# ЛОГИКА ДЛЯ VK
# ==========================================
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

def get_vk_stream(vk_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
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
            if stream_url:
                return {"url": stream_url, "title": info.get('title') or "", "thumbnail": info.get('thumbnail') or ""}
    except Exception:
        pass
    return None

# ==========================================
# ЛОГИКА ДЛЯ RUTUBE (ТОЧНАЯ КОПИЯ PYQT-СКРИПТА)
# ==========================================
def _rutube_api_request(url, ref=None, json_mode=False):
    """Точная копия api_get_ex из PyQt-скрипта."""
    session = requests.Session()
    session.verify = False
    headers = RUTUBE_HEADERS.copy()
    if ref:
        headers["Referer"] = ref
        try:
            session.get(ref, headers=headers, timeout=10) # Прогрев
        except Exception:
            pass
    try:
        r = session.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        return r.json() if json_mode else r.text
    except Exception:
        return None
    finally:
        session.close()

def _pick_best_rutube_stream(m3u8_text, base_url):
    """Парсит master m3u8, выбирает лучший поток (с rtbcdn.ru)."""
    lines = m3u8_text.splitlines()
    streams = []
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF:"):
            url = ""
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                url = lines[j].strip()
            if not url or url.startswith("#"):
                continue
            if not url.startswith("http"):
                url = urljoin(base_url, url)
            
            m = re.search(r"RESOLUTION=\d+x(\d+)", line)
            h = int(m.group(1)) if m else 0
            streams.append({"url": url, "height": h})
    
    if not streams:
        return base_url
    
    # Сортируем по высоте кадра (от большего к меньшему)
    streams.sort(key=lambda s: -s["height"])
    
    # Проверяем живость через HEAD
    for s in streams:
        try:
            r = requests.head(s["url"], allow_redirects=True, timeout=5, headers=RUTUBE_HEADERS, verify=False)
            if r.status_code == 200:
                if "rtbcdn.ru" in s["url"]:
                    return s["url"]
        except Exception:
            pass
    
    for s in streams:
        try:
            r = requests.head(s["url"], allow_redirects=True, timeout=5, headers=RUTUBE_HEADERS, verify=False)
            if r.status_code == 200:
                return s["url"]
        except Exception:
            pass
    return streams[0]["url"] if streams else base_url

def get_rutube_stream(vk_url):
    match = re.search(r'/(?:live/|video/)?([a-f0-9]{32})', vk_url)
    if match:
        video_id = match.group(1)
        # 1. Запрос к API (по http, без параметров)
        api_url = f"http://rutube.ru/api/play/options/{video_id}"
        data = _rutube_api_request(api_url, ref="http://rutube.ru/", json_mode=True)
        
        if isinstance(data, dict):
            stream_url = None
            live = data.get("live_streams")
            if isinstance(live, dict):
                hls = live.get("hls")
                if hls and isinstance(hls, list) and hls[0].get("url"):
                    master_url = hls[0]["url"]
                    # 2. Второй запрос к master m3u8
                    m3u8_text = _rutube_api_request(master_url)
                    if m3u8_text:
                        stream_url = _pick_best_rutube_stream(m3u8_text, master_url)
            
            if not stream_url:
                vb = data.get("video_balancer")
                if vb and isinstance(vb, dict):
                    stream_url = vb.get("m3u8")
            
            if stream_url:
                return {
                    "url": stream_url,
                    "title": data.get('title', ''),
                    "thumbnail": data.get('thumbnail_url', '')
                }
    return None

# ==========================================
# ГЛАВНЫЙ ЦИКЛ
# ==========================================
def get_stream_info(vk_url):
    if "rutube.ru" in vk_url or "rutube.sport" in vk_url:
        return get_rutube_stream(vk_url)
    elif "vk.com" in vk_url or "vkvideo.ru" in vk_url:
        return get_vk_stream(vk_url)
    return None

def main():
    print(f"{C_CYAN}{C_BOLD}=== Ultimate VK & Rutube Auto-Update ==={C_RESET}")
    if not os.path.exists(CONFIG_FILE):
        print(f"{C_RED}Файл vk_config.json не найден!{C_RESET}")
        return
        
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    all_channels = []
    
    for cat_id in config.get("categories", []):
        print(f"{C_CYAN}[*] Загрузка VK категории: {cat_id}{C_RESET}")
        all_channels.extend(get_streams_from_category(cat_id))
        
    for ch in config.get("channels", []):
        if "group" not in ch or not ch["group"]:
            if "rutube.ru" in ch['url']: ch["group"] = "📼 Rutube"
            elif "vk.com" in ch["url"] or "vkvideo.ru" in ch["url"]: ch["group"] = "🎬 VK Video"
            else: ch["group"] = "📦 Разное"
        all_channels.append(ch)

    if not all_channels:
        print(f"{C_YELLOW}[!] Каналы не найдены.{C_RESET}")
        return

    print(f"\n{C_CYAN}[*] Всего каналов: {len(all_channels)}. Начинаем проверку...{C_RESET}\n")
    
    lines = ["#EXTM3U"]
    progress = Progress(len(all_channels))
    
    for ch in all_channels:
        info = get_stream_info(ch['url'])
        
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
            if "rutube.ru" in ch['url'] or "rutube.sport" in ch['url']:
                lines.append("#EXTVLCOPT:http-referrer=https://rutube.ru/")
                lines.append("#EXTVLCOPT:http-origin=https://rutube.ru")
            elif "vk.com" in ch['url'] or "vkvideo.ru" in ch['url']:
                lines.append("#EXTVLCOPT:http-referrer=https://vk.com/")
                lines.append("#EXTVLCOPT:http-origin=https://vk.com")
                
            lines.append(info["url"])
            progress.update(True, final_name)
        else:
            progress.update(False, ch["name"])
            
    print("\n")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")
    
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
