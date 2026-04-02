from datetime import datetime
import json
import os
import re
import glob
from bs4 import BeautifulSoup, Comment
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

def simplify_receipt(html_file, output_file):
    """
    Парсит HTML кассового чека от Платформы ОФД
    и преобразует в упрощённый табличный формат.
    """
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # # --- 1. Извлекаем информацию о магазине ---
    shop_info = {}
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        match = re.search(r"ИНН[\s:]*(\d{12}|\d{10})\b", text)
        if match:
            shop_info['ИНН'] = match.group(1)

    # Адрес (длинный span после организации)
    for span in soup.find_all('span'):
        text = span.get_text(strip=True)
        if re.search(r'\d{6}.*обл|г\.\s|ул\s|д\.\s', text):
            shop_info['Адрес'] = text
            break

    # Дата и время чека
    for span in soup.find_all('span'):
        text = span.get_text(strip=True)
        if re.search(r'\d\d\.\d\d\.\d\d\d\d \d\d\:\d\d', text):
            date_time = text
            break


        # --- 2. Извлекаем информацию о товаре ---
    products = []
    product_dict = {}

    # Находим открывающий комментарий <!-- Предоплата -->
    prepay_start = soup.find(
        string=lambda text: isinstance(text, Comment)
        and text.strip() == 'Предоплата'
    )
        
    # Собираем всё содержимое между <!-- Предоплата --> и <!-- /Предоплата -->
    if prepay_start:
        prepay_content = []
        current = prepay_start.next_sibling
        
        while current:
            # Проверяем, не встретили ли закрывающий комментарий
            if isinstance(current, Comment) and current.strip() == '/Предоплата':
                break
            
            # Добавляем элементы в список
            if current.name:  # Если это тег (не текст)
                prepay_content.append(current)
            elif isinstance(current, str) and current.strip():  # Если это непустой текст
                prepay_content.append(current.strip())
            
            current = current.next_sibling

    for index, span in enumerate(prepay_content):
        counter = index + 1
        product_dict[counter] = {}
        span_itemname_block = span.find_all(string=lambda text: isinstance(text, Comment) and text.strip() == 'itemName')
        for item in span_itemname_block:
            name = item.find_next('b').get_text(strip=True)
            name_match = re.match(r'(\d+):\s(.+)', name)
            product_dict[counter]['num'] = name_match.group(1)
            product_dict[counter]['name'] = name_match.group(2)

        span_cost_block = span.find_all(string=lambda text: isinstance(text, Comment) and text.strip() == 'Цена')
        for item in span_cost_block:
            name = item.find_next('b').get_text(strip=True)
            price_match = re.search(
                r'((\d+.\d+)|(\d+))([а-яА-Я]+)\Wx((\d+.\d+)|(\d+))',
                name,
            )
            product_dict[counter]['quantity'] = price_match.group(1)
            product_dict[counter]['unit'] = price_match.group(4)
            product_dict[counter]['price'] = price_match.group(5)


        span_totalcost_block = span.find_all(string=lambda text: isinstance(text, Comment) and text.strip() == 'Общая стоимость позиции')
        for item in span_totalcost_block:
            name = item.find_next('td', align='right').get_text(strip=True)
            product_dict[counter]['total'] = name


        span_valrate_block = span.find_all(string=lambda text: isinstance(text, Comment) and text.strip() == 'Ставка НДС')
        for item in span_valrate_block:
            name = item.find_next('td', align='right').get_text(strip=True)
            product_dict[counter]['vat_rate'] = name


        span_fragment_block = span.find_all(string=lambda text: isinstance(text, Comment) and text.strip() == 'Fragment - field')
        for item in span_fragment_block:
            name = item.find_next('td', align='right').get_text(strip=True)
            product_dict[counter]['code'] = name

        if product_dict[counter].get('name'):
            products.append(product_dict[counter])


    # ============================
    # ГЕНЕРАЦИЯ JSON
    # ============================
    json_output_file = str(output_file).replace('.html', '.json')
    generate_json_from_receipt(shop_info, date_time, products, json_output_file)


def generate_json_from_receipt(shop_info, data_time, products, output_file):
        """
        Генерирует JSON из распарсенных данных чека.
        """
        # Парсим дату
        date_str = data_time
        try:
            # Попробуем парсить формат "DD.MM.YYYY HH:MM"
            date_obj = datetime.strptime(date_str, '%d.%m.%Y %H:%M')
        except (ValueError, AttributeError):
            # Если не получилось, используем текущее время
            date_obj = datetime.now()
    
        # Формируем ISO 8601 формат (YYYY-MM-DDTHH:MM:SS)
        datetime_str = date_obj.strftime('%Y-%m-%dT%H:%M:%S')

        # Парсим ИНН
        inn_text = shop_info.get('ИНН', '')
        store_inn = inn_text.replace('ИНН', '').strip() if inn_text else ''
        
        # Адрес
        store_address = shop_info.get('Адрес', '')
        
        # Преобразуем товары в нужный формат
        products_json = []
        for p in products:
            product_entry = {
                "num": p.get('num', ''),
                "name": p.get('name', ''),
                "quantity": float(p.get('quantity', 0)),
                "unit": p.get('unit', ''),
                "unitPrice": float(p.get('price', 0)),
                "totalPrice": float(p.get('total', 0).replace(',', '.')) if p.get('total') else 0.0,
                "code": p.get('code', '')
            }
            products_json.append(product_entry)
        
        # Формируем JSON
        receipt_json = {
            "dateTime": datetime_str,
            "storeINN": store_inn,
            "storeAdress": store_address,
            "products": products_json
        }
        
        # Сохраняем JSON
        with open(PROJECT_ROOT / 'receipts_inbox' / store_inn /output_file, 'w', encoding='utf-8') as f:
            json.dump(receipt_json, f, ensure_ascii=False, indent=4)
        
        print(f"✅ JSON сохранён: {os.path.basename(output_file)}")
        return receipt_json


def process_all_receipts(input_dir, output_dir):
    """Пакетная обработка всех HTML-файлов."""
    os.makedirs(output_dir, exist_ok=True)

    html_files = sorted(glob.glob(os.path.join(input_dir, 'email_*.html')))
    print(f"Найдено файлов: {len(html_files)}")

    results = []
    for html_file in html_files:
        basename = os.path.basename(html_file)
        output_file = os.path.join(output_dir, basename)
        try:
            data = simplify_receipt(html_file, output_file)
            results.append({'file': basename, 'status': 'OK', 'data': data})
        except Exception as e:
            print(f"❌ Ошибка в {basename}: {e}")
            results.append({'file': basename, 'status': 'ERROR', 'error': str(e)})

    # Итоговый отчёт
    print(f"\n{'='*50}")
    print(f"Обработано: {len(results)}")
    print(f"Успешно: {sum(1 for r in results if r['status'] == 'OK')}")
    print(f"Ошибок: {sum(1 for r in results if r['status'] == 'ERROR')}")

    return results


if __name__ == '__main__':
    INPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'html')
    OUTPUT_DIR = PROJECT_ROOT / "receipts_inbox" / "5257056036"

    process_all_receipts(INPUT_DIR, OUTPUT_DIR)