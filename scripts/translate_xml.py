import xml.etree.ElementTree as ET
from deep_translator import GoogleTranslator
import os
import json
import re
import time
import sys
import shutil

# --- НАСТРОЙКИ ---
INPUT_FILE = 'input.xml'
OUTPUT_FILE = 'output_translated.xml'
CACHE_FILE = 'translation_cache.json'
BACKUP_FILE = 'translation_cache.json.bak'

def has_cyrillic(text):
    if not text: return False
    return bool(re.search('[а-яА-Я]', text))

def create_manual_backup():
    """Ручной бэкап с датой (-l)."""
    if os.path.exists(CACHE_FILE):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        manual_bak = f"translation_cache_{timestamp}.json.bak"
        shutil.copy2(CACHE_FILE, manual_bak)
        print(f"[SUCCESS] Ручной бэкап создан: {manual_bak}")
    else:
        print("[ERROR] База не найдена.")

def load_cache():
    """Загрузка базы + Авто-бэкап перед работой."""
    if os.path.exists(CACHE_FILE):
        shutil.copy2(CACHE_FILE, BACKUP_FILE)
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

def build_text_map(cache):
    text_map = {}
    for entry in cache.values():
        if isinstance(entry, dict):
            en_txt = entry.get("en")
            ru_txt = entry.get("ru")
            if en_txt and ru_txt and has_cyrillic(str(ru_txt)):
                text_map[en_txt] = ru_txt
    return text_map

def safe_translate(translator, text):
    while True:
        try:
            return translator.translate(text)
        except Exception as e:
            if "429" in str(e).lower() or "too many requests" in str(e).lower():
                print(f"\n[!] Google Limit. Пауза 60 сек...")
                time.sleep(60)
                continue 
            return None

def process_xml(mode):
    if not os.path.exists(INPUT_FILE):
        print(f"Ошибка: {INPUT_FILE} не найден!")
        return

    cache = load_cache()
    
    try:
        tree = ET.parse(INPUT_FILE)
        root = tree.getroot()
    except Exception as e:
        print(f"Ошибка XML: {e}"); return

    loc_blocks = root.findall('.//Localisation[@Key]')
    total_count = len(loc_blocks)
    
    print(f"РЕЖИМ: {mode} | База: {len(cache)}")
    print("-" * 120)

    translator = GoogleTranslator(source='en', target='ru')
    fast_map = build_text_map(cache) if mode == "-t" else {}
    updates_count = 0

    for index, block in enumerate(loc_blocks, start=1):
        key = block.get('Key')
        # Ищем тег Translation внутри блока Localisation
        trans_elem = block.find('.//Translation')
        if trans_elem is None or not key: continue
        
        raw_text = trans_elem.text if trans_elem.text else ""
        original_text = raw_text.strip()
        if not original_text: continue

        # --- РЕЖИМ ЧТЕНИЯ (-r) ---
        if mode == "-r":
            is_russian = has_cyrillic(original_text)
            status_log = None
            if key not in cache:
                if is_russian:
                    cache[key] = {"en": original_text, "ru": original_text}
                    status_log = "[IMPORT RU]"
                else:
                    cache[key] = {"en": original_text, "ru": ""}
                    status_log = "[IMPORT EN]"
                updates_count += 1
            else:
                if is_russian:
                    if cache[key].get("en") and not has_cyrillic(cache[key]["en"]):
                        cache[key]["ru"] = original_text
                        status_log = "[LINK RU]"
                    else:
                        cache[key]["en"] = original_text
                        cache[key]["ru"] = original_text
                        status_log = "[UPDATE RU]"
                    updates_count += 1
                else:
                    if cache[key].get("en") != original_text:
                        cache[key]["en"] = original_text
                        status_log = "[UPDATE EN]"
                        updates_count += 1
            continue

        # --- РЕЖИМ ПЕРЕВОДА (-t) ---
        status = ""; final_translation = ""
        cache_entry = cache.get(key)

        if has_cyrillic(original_text):
            cache[key] = {"en": original_text, "ru": original_text}
            status = "[LEARN]   "; final_translation = original_text
        elif isinstance(cache_entry, dict) and cache_entry.get("en") == original_text and cache_entry.get("ru"):
            final_translation = cache_entry["ru"]; status = "[DATABASE]"
        elif original_text in fast_map:
            final_translation = fast_map[original_text]
            cache[key] = {"en": original_text, "ru": final_translation}
            status = "[REUSE]   "
        elif isinstance(cache_entry, dict) and cache_entry.get("ru") and has_cyrillic(str(cache_entry["ru"])):
            final_translation = cache_entry["ru"]
            cache[key]["en"] = original_text
            status = "[RESERVE] "
        else:
            translated = safe_translate(translator, original_text)
            if translated:
                cache[key] = {"en": original_text, "ru": translated}
                fast_map[original_text] = translated
                final_translation = translated; status = "[GOOGLE]  "
                updates_count += 1
                if updates_count % 20 == 0: save_cache(cache)
            else:
                final_translation = original_text; status = "[FAILED]  "

        # Записываем чистый текст в элемент
        trans_elem.text = final_translation
        
        if status != "[DATABASE]" and status != "":
             print(f"[{index}/{total_count}] {status} {key[:30]:<30} | {original_text[:40]}... -> {final_translation[:40]}...")

    save_cache(cache)
    
    if mode == "-t":
        # Сохраняем XML (он будет без CDATA и с &lt;)
        tree.write(OUTPUT_FILE, encoding='utf-8', xml_declaration=True)
        
        # ФИКС CDATA: Читаем файл как текст и правим теги
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Улучшенный Regex: ищет <Translation Любые_Атрибуты> Текст </Translation>
        # Группа 1: Открывающий тег с атрибутами
        # Группа 2: Сам текст внутри
        fixed_content = re.sub(r'(<Translation[^>]*>)(.*?)(</Translation>)', r'\1<![CDATA[\2]]>\3', content)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
            
    print("-" * 120 + f"\nЗавершено. Изменений: {updates_count}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-l":
        create_manual_backup()
    else:
        m = sys.argv[1] if len(sys.argv) > 1 else "-t"
        process_xml(m)