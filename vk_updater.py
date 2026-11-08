import json
import yt_dlp
import requests
import os
import uuid

CONFIG_FILE = "vk_config.json"
OUTPUT_FILE = "vk_live.m3u"

def get_streams_from_category(category_id):
    url = f"https://api.live.vkvideo.ru/v1/catalog/public_video_streams/category/{category_id}/stream/?limit=100"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://live.vkvideo.ru",
        "Referer": "https://live.vkvideo.ru/",
        "X-App": "streams_web",
        "X-From-Id": str(uuid.uuid4()),
        "X-Referer": "https://live.vkvideo.ru/",
        "X-Super-Referer": "https://live.vkvideo.ru/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # НОВАЯ СТРУКТУРА: ищем data -> streamBlogs
        streams = data.get("data", {}).get("streamBlogs", [])
        
        if not streams:
            print(f"[!] В ответе не найден список streamBlogs.")
            return []
            
        result = []
        for s in streams:
            blog = s.get("blog", {})
            blog_url = blog.get("blogUrl")
            
            if not blog_url:
                continue
                
            # 1. Название
            raw_name = blog.get("title") or blog.get("owner", {}).get("displayName") or blog_url
            name = raw_name[:50] + "..." if len(raw_name) > 50 else raw_name
            name = name.replace(",", " ")
            
            # 2. Ссылка на стрим (используем канонический URL VK Live)
            channel_url = f"https://live.vkvideo.ru/{blog_url}"
            
            # 3. Логотип
            logo = blog.get("owner", {}).get("avatarUrl") or blog.get("coverUrl") or ""
            
            result.append({"name": name, "url": channel_url, "logo": logo})
                
        print(f"Найдено {len(result)} стримов в категории {category_id}")
        return result
    except Exception as e:
        print(f"Ошибка при получении категории {category_id}: {e}")
        return []

def get_stream_url(vk_url):
    ydl_opts = {
        'quiet': True, 'no_warnings': True,
        'format': 'best[protocol^=m3u8]',
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://vk.com/'
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(vk_url, download=False)
            for fmt in info.get('formats', []):
                if fmt.get('protocol') == 'm3u8' and fmt.get('url'):
                    return fmt['url']
            return info.get('url')
    except Exception as e:
        # Если yt-dlp не смог распарсить (например, стрим офлайн), возвращаем None
        return None

def main():
    if not os.path.exists(CONFIG_FILE):
        print("Файл vk_config.json не найден!")
        return
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    all_channels = []
    for cat_id in config.get("categories", []):
        print(f"Обработка категории: {cat_id}")
        all_channels.extend(get_streams_from_category(cat_id))
        
    for ch in config.get("channels", []):
        all_channels.append(ch)

    lines = ["#EXTM3U"]
    success_count = 0
    
    for ch in all_channels:
        print(f"Проверка: {ch['name']}...")
        stream_url = get_stream_url(ch['url'])
        
        if stream_url:
            success_count += 1
            logo_attr = f' tvg-logo="{ch["logo"]}"' if ch.get("logo") else ""
            lines.append(f'#EXTINF:-1{logo_attr} group-title="📺 VK Live",{ch["name"]}')
            lines.append("#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            lines.append(stream_url)
            print(f"  -> Успех")
        else:
            print(f"  -> Пропущено (офлайн или нет доступа)")
            
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")
        
    print(f"\nГотово! Файл {OUTPUT_FILE} обновлен. Успешно добавлено: {success_count} из {len(all_channels)}")

if __name__ == "__main__":
    main()
