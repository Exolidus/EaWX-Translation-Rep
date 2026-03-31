import os
import re
from deep_translator import GoogleTranslator

def translate_localization():
    input_file = 'input.txt'
    output_file = 'output.txt'
    target_lang = 'ru'
    batch_size = 10 
    
    if not os.path.exists(input_file):
        print(f"Ошибка: Файл {input_file} не найден.")
        return

    translator = GoogleTranslator(source='auto', target=target_lang)
    
    # 1. Индексация уже переведенных строк (подхват)
    translated_keys = set()
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f_check:
            for line in f_check:
                if ',' in line:
                    key, _ = line.split(',', 1)
                    translated_keys.add(key.strip())
    
    # 2. Чтение входного файла (индексация в памяти)
    data_index = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if ',' in line:
                key, text = line.split(',', 1)
                data_index.append({'key': key.strip(), 'text': text.strip()})
            else:
                data_index.append({'key': None, 'raw': line})

    print(f"Всего строк: {len(data_index)}. Пропущено (уже есть в output): {len(translated_keys)}")
    print("-" * 50)

    # 3. Обработка
    translated_count = 0
    
    try:
        # Режим 'a' позволяет дописывать файл, не ломая структуру
        with open(output_file, 'a', encoding='utf-8') as f_out:
            for i, item in enumerate(data_index, 1):
                key = item.get('key')
                
                # Если ключ уже переведен — идем дальше
                if key and key in translated_keys:
                    continue

                if key is not None:
                    original_text = item['text']
                    
                    if original_text and original_text.upper() != "TODO":
                        try:
                            # Перевод
                            translated = translator.translate(original_text)
                            
                            # ПРАВИЛО: перевод без скобок [] () {}
                            clean_translation = re.sub(r'[\(\[\{].*?[\)\]\}]', '', translated).strip()
                            
                            # Консоль: №) исходник --- перевод
                            print(f"{i}) {original_text[:30]}... --- {clean_translation[:30]}...")
                            
                            # Сохранение структуры КЛЮЧ,ЗНАЧЕНИЕ
                            f_out.write(f"{key},{clean_translation}\n")
                            translated_count += 1
                            
                            # Автосохранение каждые 10 строк
                            if translated_count % batch_size == 0:
                                f_out.flush()
                                os.fsync(f_out.fileno())
                                print(f">>> Сохранено {translated_count} строк.")
                                
                        except Exception as e:
                            print(f"{i}) Ошибка на ключе {key}: {e}")
                    else:
                        # Если текст пустой или TODO
                        f_out.write(f"{key},{original_text}\n")
                else:
                    # Пустые или некорректные строки сохраняем "как есть"
                    f_out.write(item.get('raw', '\n'))

    except KeyboardInterrupt:
        print("\n[!] Остановка. Прогресс сохранен.")
    finally:
        print("-" * 50)
        print(f"Готово. Проверьте {output_file}")

if __name__ == "__main__":
    translate_localization()