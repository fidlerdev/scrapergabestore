import os
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests
from openpyxl import Workbook
from pathlib import Path
from time import sleep

# Конфигурация
BASE_URL = (
    "https://gabestore.ru/search/next?"
    "series=&ProductFilter%5BsortName%5D=views"
    "&ProductFilter%5BpriceRange%5D=&ProductFilter%5BpriceFrom%5D="
    "&ProductFilter%5BpriceTo%5D=&ProductFilter%5Bavailable%5D=0"
    "&ProductFilter%5Bavailable%5D=1&page={}"
)

PROGRESS_FILE = "progress.json"
IMAGES_DIR = "game_images"
EXCEL_FILE = "games.xlsx"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Создаем папки
Path(IMAGES_DIR).mkdir(exist_ok=True)


def get_last_page():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("last_page", 1)
    return 1


def save_last_page(page):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_page": page}, f, ensure_ascii=False, indent=2)


def download_image(img_url, filename):
    try:
        response = requests.get(img_url, headers=HEADERS, stream=True)
        response.raise_for_status()
        ext = img_url.split(".")[-1].split("?")[0]
        filename = f"{filename}.{ext}"
        path = os.path.join(IMAGES_DIR, filename)
        with open(path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return filename
    except Exception as e:
        print(f"Ошибка при скачивании изображения: {e}")
        return None


def parse_game_page(url):
    response = requests.get(url, headers=HEADERS, timeout=10)
    sleep(2)
    soup = BeautifulSoup(response.text, "lxml")

    game_data = {}
    table_rows = soup.select(".b-card__table .b-card__table-item")
    for row in table_rows:
        title_div = row.find("div", class_="b-card__table-title")
        value_div = row.find("div", class_="b-card__table-value")
        if title_div and value_div:
            key = title_div.get_text(strip=True)
            val = value_div.get_text(strip=True)
            if key in ["Жанр", "Платформа", "Дата выхода", "Издатель", "Разработчик"]:
                game_data[key] = val

    tab_container = soup.find("div", class_="b-tabs b-tabs--content js-tab")
    tab_map = {}

    if tab_container:
        for header in tab_container.select(".b-tabs__head-item"):
            index = header.get("data-tab-index")
            title = header.get_text(strip=True).lower()
            if index and title:
                tab_map[index] = title

        content_blocks = tab_container.select(".js-tab-content")
    else:
        content_blocks = []

    tab_content_map = {}
    for block in content_blocks:
        index = block.get("data-tab-index")
        if index and index in tab_map:
            title = tab_map[index]
            text = block.get_text(strip=True, separator="\n")
            tab_content_map[title] = text

    subinfo = soup.find("div", class_="b-card__subinfo")
    additional_data = {}
    if subinfo:
        items = subinfo.find_all("div", class_="b-card__subinfo-item")
        for item in items:
            head = item.find("div", class_="b-card__subinfo-head")
            body = item.find("div", class_="b-card__subinfo-body")
            if head and body:
                key = head.get_text(strip=True)
                val = body.get_text(strip=True)
                additional_data[key] = val

    result = {
        **game_data,
        "Описание": tab_content_map.get("описание", ""),
        "Системные требования": tab_content_map.get("системные требования", ""),
        "Активация": tab_content_map.get("активация", ""),
        **additional_data,
    }

    return result


def parse_search_page(page):
    url = BASE_URL.format(page)
    response = requests.get(url, headers=HEADERS, timeout=10)
    sleep(2)
    if response.status_code != 200:
        print(f"Ошибка загрузки страницы {page}: {response.status_code}")
        return []

    try:
        data = response.json()
        html = data.get("html", "")
    except Exception as e:
        print(f"Ошибка парсинга JSON на странице {page}: {e}")
        return []

    soup = BeautifulSoup(html, "lxml")
    items = soup.select(".shop-item")
    results = []

    for item in items:
        name_tag = item.select_one(".shop-item__name")
        price_tag = item.select_one(".shop-item__price-current")
        link_tag = item.select_one(".shop-item__image")
        img_tag = item.select_one(".shop-item__image img")

        if not all([name_tag, price_tag, link_tag, img_tag]):
            continue

        name = name_tag.get_text(strip=True)
        price = price_tag.get_text(strip=True)
        link = urljoin("https://gabestore.ru", link_tag["href"]).strip()
        img_url = urljoin("https://gabestore.ru", img_tag["src"]).strip()

        # Скачиваем изображение
        img_filename = download_image(img_url, name.replace(" ", "_"))

        print(f"Обрабатываем игру: {name} | Цена: {price}")

        try:
            details = parse_game_page(link)  # Получаем детальную информацию
        except Exception as e:
            print(f"Ошибка при обработке страницы игры: {e}")
            details = {}

        full_data = {
            "Название": name,
            "Цена": price,
            "Ссылка": link,
            "Картинка": img_filename or "",
            **details,
        }

        results.append(full_data)

    return results


def save_to_excel(data, filename=EXCEL_FILE):
    wb = Workbook()
    ws = wb.active
    ws.title = "Игры"

    headers = list(data[0].keys()) if data else []
    ws.append(headers)

    for row in data:
        ws.append([row.get(h, "") for h in headers])

    wb.save(filename)
    print(f"Данные сохранены в файл: {filename}")


def main(start_page=1, max_pages=10):
    current_page = start_page
    all_games = []

    try:
        while current_page <= max_pages:
            print(f"\n{'=' * 20} Обработка страницы {current_page} {'=' * 20}")
            games = parse_search_page(current_page)
            if not games:
                print("Больше нет данных или произошла ошибка.")
                break
            all_games.extend(games)
            save_last_page(current_page)
            current_page += 1
    except KeyboardInterrupt:
        print("\n⛔ Прервано пользователем. Сохраняю текущие данные...")
    finally:
        if all_games:
            save_to_excel(all_games)
        print("✅ Работа завершена.")


if __name__ == "__main__":
    start_page = get_last_page()
    main(start_page=start_page, max_pages=3000)
