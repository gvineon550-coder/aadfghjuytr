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

# 📌 ОГРОМНЫЙ СЛОВАРЬ ПЕРЕВОДОВ (Латиница -> Кириллица для EPG)
MANUAL_MAP = {
    # Федеральные
    "channel one": "первый канал", "1tv": "первый канал",
    "russia 1": "россия 1", "russia 24": "россия 24", "russia k": "россия к",
    "match": "матч", "match arena": "матч арена", "match boets": "матч боец",
    "match igra": "матч игра", "match strana": "матч страна", "match ultra": "матч ультра",
    "match premier": "матч премьер", "match planeta": "матч планета",
    "ntv": "нтв", "channel 5": "пятый канал", "5 kanal": "пятый канал",
    "carousel": "карусель", "karusel": "карусель", "otr": "отр",
    "tv centr": "тв центр", "tvc": "тв центр", "ren tv": "рен тв", "rentv": "рен тв",
    "spas": "спас", "sts": "стс", "domashniy": "домашний", "tv 3": "тв-3", "tv3": "тв-3",
    "friday": "пятница", "zvezda": "звезда", "mir": "мир", "tnt": "тнт",
    "muz tv": "муз-тв", "muztv": "муз-тв", "che": "че", "tv 21": "тв 21", "tv21": "тв 21",
    "u": "у", "y": "у", "tv brics": "tv brics", "mir 24": "мир 24",

    # Кино и сериалы
    "dom kino": "дом кино", "domkino": "дом кино", "dom kino premium": "дом кино премиум",
    "kinopokaz": "кинопоказ", "kinosemja": "киносемья", "kinopremyera": "кинопремьера",
    "kinomix": "киномикс", "kinosvidanie": "киносвидание", "indiyskoye kino": "индийское кино",
    "kinokomedija": "кинокомедия", "kinouzhas": "киноужас", "ostrosyuzhetnoye": "остросюжетное",
    "evrokino": "еврокино", "illuzion": "иллюзион", "tv1000": "tv1000", "viju tv1000": "viju tv1000",
    "kinohit": "кинохит", "komedia": "комедия", "komediynoe": "комедийное",
    "muzhskoe kino": "мужское кино", "nashe novoe kino": "наше новое кино",
    "nash kinopokaz": "наш кинопоказ", "rodnoe kino": "родное кино", "russkiy roman": "русский роман",
    "russkiy bestseller": "русский бестселлер", "russkiy detektiv": "русский детектив",
    "premialnoe": "премиальное", "priklyucheniya": "приключения", "shokiruyushchee": "шокирующее",
    "velvet": "velvet", "dorama": "дорама", "start": "start", "star cinema": "star cinema", "star family": "star family",

    # Познавательные
    "nauka": "наука", "moya planeta": "моя планета", "zhivaya priroda": "живая природа",
    "zoopark": "зоопарк", "v mire zhivotnykh": "в мире животных", "dikij": "дикий",
    "dikaya okhota": "дикая охота", "dikaya rybalka": "дикая рыбалка", "okhota i rybalka": "охота и рыбалка",
    "ohotnik i rybolov": "охотник и рыболов", "rybolov": "рыболов", "usadba": "усадьба",
    "zagorodnaya zhizn": "загородная жизнь", "zdorovoe tv": "здоровое тв", "doctor": "доктор",
    "domashnie zhivotnye": "домашние животные", "viju explore": "viju explore", "viju history": "viju history",
    "viju nature": "viju nature", "viju planet": "viju planet", "viju": "viju", "viasat": "viju",
    "travel adventure": "travel adventure", "foodtime": "foodtime", "kuhnya": "кухня", "kulinar": "кулинар",
    "pro business": "pro business", "pro lyubov": "про любовь", "prosveshchenie": "просвещение",
    "rbc": "рбк", "rbk": "рбк", "izvestia": "известия", "unknown russia": "неизвестная россия",
    "konkurent": "конкурент", "fashion": "fashion", "shopping live": "shopping live",

    # Детские
    "mult": "мульт", "multilandia": "мультиландия", "mama": "мама", "v gostyakh u skazki": "в гостях у сказки",
    "bober": "бобер", "gulli girl": "gulli girl", "tiji": "tiji", "da vinci": "da vinci",
    "supergeroi": "супергерои", "detskiy": "детский", "nick jr": "nick jr", "nickelodeon": "nickelodeon",
    "cartoon classics": "cartoon classics", "lapki live": "лапки live",

    # Музыка
    "shanson": "шансон", "europa plus": "европа плюс", "zhara": "жара", "ru tv": "ru tv",
    "rutv": "ru tv", "russian musicbox": "russian musicbox", "muz": "муз", "muzyka pervogo": "музыка первого",
    "muzyka live": "музыка live", "1hd": "1hd", "hit": "hit", "bridge": "bridge",
    "dancehits80": "dancehits80", "fon music": "фон музик", "mcm top": "mcm top", "live music channel": "live music channel",

    # Спорт
    "khl": "кхл", "viju sport": "viju sport", "setanta sports": "setanta sports",
    "extreme sports": "extreme sports", "mma tv": "mma tv", "boks tv": "бокс тв",
    "okko": "okko", "sportivnyy": "спортивный", "match tv": "матч тв",

    # Разное
    "2x2": "2х2", "2na2": "2х2", "360": "360", "365 days tv": "365 дней", "365 dnej": "365 дней",
    "black": "black", "red": "red", "scifi": "sci fi", "art": "art", "ani": "ani",
    "avto24": "авто24", "auto plus": "авто плюс", "balabol": "балабол", "blokbaster": "блокбастер",
    "classic music": "классик музик", "drive": "drive", "enisey": "енисей", "fan": "fan",
    "fox": "fox", "fox life": "fox life", "horoshee kino": "хорошее кино", "insayt": "инсайт",
    "istoki": "истоки", "kapitan fantastika": "капитан фантастика", "kino 24": "кино 24",
    "kino tv": "кино тв", "kongress": "конгресс тв", "kvn": "квн", "maidan": "майдан",
    "mosfilm": "мосфильм", "moskva 24": "москва 24", "moy mir": "мой мир", "moya stikhiya": "моя стихия",
    "nano": "нано", "nashe": "наше", "nevskiy": "невский", "nst": "нст", "o": "о",
    "perviy otdel": "первый отдел", "pes": "пёс", "prodvizhenie": "продвижение",
    "radost moya": "радость моя", "retro": "ретро", "rt": "rt", "rtg": "rtg",
    "rtvi": "rtvi", "sankt peterburg": "санкт-петербург", "saphire": "сапфир",
    "sarafan": "сарафан", "shef": "шеф", "skoraya pomoshch": "скорая помощь",
    "smile tv": "smile tv", "smotrim": "смотрим", "solnce": "солнце", "solovyov live": "соловьёв live",
    "songtv": "songtv", "soyuz": "союз", "subbota": "суббота", "svoboda": "свобода",
    "t24": "т24", "telecafe": "телекафе", "teledom": "теледом", "tnv": "тнв",
    "tochka rf": "точка рф", "tochka otryva": "точка отрыва", "tooku": "тооку",
    "tsargrad": "царьград", "udar": "удар", "univer": "универ", "vitrina": "витрина",
    "vkus": "вкус", "vmeste rf": "вместе-рф", "voprosy i otvety": "вопросы и ответы",
    "vremya": "время", "zhivi": "живи", "afontovo": "афонтово", "amedia hit": "amedia hit",
    "channel 8": "8 канал", "channel 10": "10 канал", "channel 12": "12 канал",
    "glazami turista": "глазами туриста", "groznyj": "грозный", "law tv": "law tv",
    "sochi live": "сочи live", "sochi 24": "сочи 24", "nasha tema": "наша тема",
    "redline": "красная линия", "krasnaya linia": "красная линия",
    "mir belogorya": "мир белогорья", "mir belagorya": "мир белогорья",
    "huzur": "хузур", "xuzur": "хузур", "vtv": "втв", "russian extreme ultra": "russian extreme ultra"
}

def log(msg: str) -> None:
    print(msg, flush=True)

def progress_bar(percent: int, length: int = 20) -> str:
    filled = int(length * percent / 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}]"

def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    # Удаляем все, что в скобках (576p, [Geo-blocked] и т.д.)
    name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', name)
    # Удаляем маркеры качества
    name = re.sub(r'\b(hd|sd|fhd|fullhd|uhd|4k|8k|2160p|1080p|720p|576p|576i|480p|480i|360p|hevc|h\.?264|h\.?265)\b', '', name)
    # Оставляем только буквы, цифры и пробелы
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def load_logos(path: str) -> dict:
    log(f"📥 Загружаем логотипы...")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logos = {item["channel"]: item["url"] for item in data 
             if item.get("channel") and item.get("url", "").startswith("http")}
    log(f"✅ Загружено {len(logos)} логотипов")
    return logos

def build_epg_mapping(url: str) -> tuple[set, dict, dict]:
    log(f"📥 Скачиваем и парсим EPG (около минуты)...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()

    source = gzip.GzipFile(fileobj=io.BytesIO(raw)) if raw[:2] == b"\x1f\x8b" else io.BytesIO(raw)
    
    epg_ids = set()
    exact_map = {}
    fuzzy_map = defaultdict(set)

    for event, elem in ET.iterparse(source, events=("end",)):
        if elem.tag == "channel":
            epg_id = elem.get("id")
            if epg_id:
                epg_ids.add(epg_id)
                for name_node in elem.findall("display-name"):
                    if name_node.text:
                        norm_name = normalize_name(name_node.text)
                        if norm_name:
                            exact_map[norm_name] = epg_id
                            for word in norm_name.split():
                                if len(word) > 2:
                                    fuzzy_map[word].add(epg_id)
            elem.clear()

    log(f"✅ EPG загружено: {len(epg_ids)} ID, {len(exact_map)} названий")
    return epg_ids, exact_map, fuzzy_map

def find_epg_id(channel_name: str, exact_map: dict, fuzzy_map: dict) -> str | None:
    norm_name = normalize_name(channel_name)
    if not norm_name:
        return None
        
    # 1. Прямое совпадение
    if norm_name in exact_map:
        return exact_map[norm_name]
        
    # 2. Перевод по словарю (самые длинные ключи в приоритете)
    sorted_keys = sorted(MANUAL_MAP.keys(), key=len, reverse=True)
    for latin_key in sorted_keys:
        if latin_key in norm_name:
            cyrillic_val = MANUAL_MAP[latin_key]
            if cyrillic_val in exact_map:
                return exact_map[cyrillic_val]
            if f"{cyrillic_val} тв" in exact_map:
                return exact_map[f"{cyrillic_val} тв"]
            if f"{cyrillic_val} hd" in exact_map:
                return exact_map[f"{cyrillic_val} hd"]
                
    # 3. Нечеткий поиск по словам
    words = sorted([w for w in norm_name.split() if len(w) > 2], key=len, reverse=True)
    for word in words:
        candidates = fuzzy_map.get(word)
        if candidates and len(candidates) == 1:
            return list(candidates)[0]
    return None

def enrich(src_path: str, out_path: str, logos: dict, epg_ids: set, exact_map: dict, fuzzy_map: dict) -> None:
    log(f"📖 Читаем плейлист...")
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    out = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    total = 0
    m_id_preserved = 0
    m_name = 0
    m_logo = 0
    unmatched = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#EXTM3U"):
            continue

        if stripped.startswith("#EXTINF"):
            total += 1
            parts = line.rsplit(",", 1)
            channel_name = parts[1].strip() if len(parts) > 1 else ""

            m = re.search(r'tvg-id="([^"]*)"', line)
            epg_id = None

            # 1. Пытаемся сохранить существующий ID (если он уже правильный)
            if m:
                original_id = m.group(1)
                if original_id in epg_ids:
                    epg_id = original_id
                    m_id_preserved += 1

            # 2. Если ID нет, ищем по названию
            if not epg_id:
                epg_id = find_epg_id(channel_name, exact_map, fuzzy_map)
                if epg_id:
                    m_name += 1
                else:
                    unmatched.append(channel_name)

            # Обновляем строку
            if epg_id:
                if 'tvg-id="' in line:
                    line = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{epg_id}"', line, count=1)
                else:
                    line = line.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-id="{epg_id}"', line, count=1)

            if 'tvg-name="' not in line:
                line = re.sub(r'(tvg-id="[^"]*")', rf'\1 tvg-name="{channel_name}"', line, count=1)

            # Логотипы
            if m:
                base_id = m.group(1).split("@", 1)[0]
                if base_id in logos:
                    m_logo += 1
                    if 'tvg-logo="' not in line:
                        line = re.sub(r'(tvg-id="[^"]*")', rf'\1 tvg-logo="{logos[base_id]}"', line, count=1)

            out.append(line)
            out.append(f"#EXTVLCOPT:http-user-agent={UA}")

        elif stripped.startswith("#EXTVLCOPT"):
            if "http-user-agent" not in stripped.lower():
                out.append(line)
        else:
            out.append(line)

    epg_total = m_id_preserved + m_name
    epg_pct = (epg_total * 100) // max(total, 1)
    logo_pct = (m_logo * 100) // max(total, 1)

    log("\n" + "━" * 45)
    log("📊 СТАТИСТИКА")
    log("━" * 45)
    log(f"Всего каналов:          {total}")
    log(f"EPG (сохранено по ID):  {m_id_preserved}")
    log(f"EPG (найдено по имени): {m_name}")
    log(f"EPG (всего):            {epg_total} ({epg_pct}%)  {progress_bar(epg_pct)}")
    log(f"Логотипы:               {m_logo} ({logo_pct}%)  {progress_bar(logo_pct)}")
    log("━" * 45)

    if unmatched:
        log(f"⚠️  Без EPG осталось {len(unmatched)} каналов. Первые 10:")
        for ch in unmatched[:10]: log(f"   - {ch}")
        if len(unmatched) > 10: log(f"   ... и еще {len(unmatched) - 10}")
        log("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    log(f"✅ Успешно записано {len(out)} строк")
    log("🎉 ГОТОВО!\n")

def main() -> None:
    log("🚀 СТАРТ")
    logos = load_logos(LOGOS_API)
    epg_ids, exact_map, fuzzy_map = build_epg_mapping(EPG_URL)
    enrich(SOURCE, OUTPUT, logos, epg_ids, exact_map, fuzzy_map)

if __name__ == "__main__":
    main()
