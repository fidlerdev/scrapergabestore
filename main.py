from pprint import pprint
import httpx
from bs4 import BeautifulSoup
from urllib import parse


base_url = (
    "https://gabestore.ru/search/next"
    "?series=&ProductFilter%5BsortName%5D=views"
    "&ProductFilter%5BpriceRange%5D=&ProductFilter%5"
    "BpriceFrom%5D=&ProductFilter%5BpriceTo%5D=&ProductFilter"
    "%5Bavailable%5D=0&ProductFilter%5Bavailable%5D=1&page={}"
)

parsed = parse.urlparse(base_url)

print(parsed.query)

qs = parse.parse_qsl(parsed.query)

print(parse.unquote(parsed.query))
print(f"{qs=} ")


def parse_game_page(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}

    response = httpx.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "lxml")

    # 1. Парсим таблицу с основными данными: Жанр, Платформа, Дата выхода, Издатель, Разработчик
    game_data = {}
    table_rows = soup.select(".b-card__table .b-card__table-item")

    for row in table_rows:
        title_div = row.find("div", class_="b-card__table-title")
        value_div = row.find("div", class_="b-card__table-value")

        if title_div and value_div:
            key = title_div.get_text(strip=True)
            value = value_div.get_text(strip=True)

            if key in ["Жанр", "Платформа", "Дата выхода", "Издатель", "Разработчик"]:
                game_data[key] = value

    # 2. Находим правильный контейнер вкладок
    tab_container = soup.find("div", class_="b-tabs b-tabs--content js-tab")

    # Если контейнер найден, строим карту заголовков
    tab_map = {}

    if tab_container:
        # Сначала получаем заголовки
        for header in tab_container.select(".b-tabs__head-item"):
            index = header.get("data-tab-index")
            title = header.get_text(strip=True).lower()
            if index and title:
                tab_map[index] = title

        # Теперь собираем текст вкладок, связанных с этим контейнером
        content_blocks = tab_container.select(".js-tab-content")
    else:
        content_blocks = []

    # 3. Создаём словарь с содержимым вкладок
    tab_content_map = {}
    for block in content_blocks:
        index = block.get("data-tab-index")
        if index and index in tab_map:
            title = tab_map[index]
            text = block.get_text(strip=True, separator="\n")
            tab_content_map[title] = (text, block)

    # 4. Получаем нужные нам данные
    description = tab_content_map.get("описание", "")[0]
    description_html = tab_content_map.get("описание", "")[1]

    requirements = tab_content_map.get("системные требования", "")[0]
    requirements_html = tab_content_map.get("системные требования", "")[1]

    activation = tab_content_map.get("активация", "")[0]
    activation_html = tab_content_map.get("активация", "")[1]

    # 3. Парсим дополнительную информацию: Поддержка языков, Регион, Сервис активации
    subinfo = soup.find("div", class_="b-card__subinfo")
    additional_data = {}

    pprint(tab_content_map)

    if subinfo:
        items = subinfo.find_all("div", class_="b-card__subinfo-item")
        for item in items:
            head = item.find("div", class_="b-card__subinfo-head")
            body = item.find("div", class_="b-card__subinfo-body")
            if head and body:
                key = head.get_text(strip=True)
                value = body.get_text(strip=True)
                additional_data[key] = value

    # 4. Объединяем всё в один словарь
    result = {
        **game_data,
        "Описание": description,
        "Описание html": description_html,
        "Системные требования": requirements,
        "Системные требования html": requirements_html,
        "Активация": activation,
        "Активация html": activation_html,
        **additional_data,
    }

    # Вывод результата
    for key, value in result.items():
        print(f"{key}: {value}\n" + "-" * 50)


if __name__ == "__main__":
    parse_game_page("https://gabestore.ru/game/metro-exodus-gold-edition")
