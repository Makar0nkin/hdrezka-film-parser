import re
import requests
from aiogram.utils.helper import Helper, HelperMode, ListItem


def field_deep_search(search_dict, field):
    fields_found = []

    for key, value in search_dict.items():

        if key == field:
            fields_found.append(value)

        elif isinstance(value, dict):
            results = field_deep_search(value, field)
            for result in results:
                fields_found.append(result)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    more_results = field_deep_search(item, field)
                    for another_result in more_results:
                        fields_found.append(another_result)

    return fields_found


def download_file(url: str, filename: str):
    r = requests.get(url, stream=True)
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)


def create_download_url(base_url: str, seg_num: int) -> str:
    url_template = re.split(r'seg-\d+', base_url)
    url_template.insert(1, f"seg-{seg_num}")
    return ''.join(url_template)


class BotStates(Helper):
    mode = HelperMode.snake_case

    CHOOSING_FILM = ListItem()
    DOWNLOADING = ListItem()


KEYS_TO_RU = {
    "name": "Название",
    "type": "Тип",
    "other": "Другое",
    "status": "Статус",
    "link": "Ссылка",
}

PARSER_STATES_TO_RU = {
    "INIT": "Начинаем...",
    "SEARCHING_URL": "Ищем ссылку для скачивания...",
    "DOWNLOADING": "Скачиваем фрагменты фильма...",
    "UNITING_SEGMENTS": "Объединяем скачанные фрагменты...",
    "MAKING_FINAL_VIDEO": "Создаем конечный файл...",
    "DONE": "Готово!",
}
