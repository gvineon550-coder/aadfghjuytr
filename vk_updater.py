import json
import yt_dlp
import requests
import os
import re

CONFIG_FILE = "vk_config.json"
OUTPUT_FILE = "vk_live.m3u"

def get_streams_from_category(category_id):
    url = f"https://api.live.vkvideo.ru/v1/catalog/public_video_streams/category/?id={category_id}&limit=100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://live.vkvideo.ru",
        "Referer": "https://live.vkvideo.ru/"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Ищем массив со стримами (структура API может немного меняться)
        streams = data.get("data", {}).get("streams", []) or data.get("data", {}).get("items", []) or data.get("streams", [])
        result = []
        
        for s in streams:
            # 1. Название (обрезаем, если слишком длинное)
            raw_name = s.get("title") or s.get("channel", {}).get("name") or "VK Live"
            name = raw_name[:50] + "..." if len(raw_name) > 50 else raw_name
            name = name.replace(",", " ") # Убираем запятые, чтобы не ломать M3U
            
            # 2. Ссылка на стрим
            channel_url = s.get("channel", {}).get("url") or s.get("url")
            
            # 3. Логотип (аватарка канала или обложка стрима)
            logo = (
                s.get("channel", {}).get("avatar") or 
                s.get("channel", {}).get("photo_200") or 
                s.get("cover", {}).get("url") or 
                s.get("preview_url") or ""
            )
            
            if channel_url:
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
        # Если стрим офлайн или приватный, yt-dlp выдаст ошибку. Просто пропускаем.
        return None

def main():
    if not os.path.exists(CONFIG_FILE):
        print("Файл vk_config.json не найден!")
        return
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    all_channels = []
    # 1. Сбор из категорий
    for cat_id in config.get("categories", []):
        print(f"Обработка категории: {cat_id}")
        all_channels.extend(get_streams_from_category(cat_id))
        
    # 2. Добавление отдельных каналов
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
            
            # Обязательный заголовок для воспроизведения VK
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
