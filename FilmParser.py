from utils import field_deep_search, download_file
# standard libraries
import re
import os
import time
import subprocess
import threading
import urllib.parse
from enum import IntEnum, auto
# external libraries
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from moviepy.editor import VideoFileClip, concatenate_videoclips


class ParserState(IntEnum):
    INIT = 0
    SEARCHING_URL = auto()
    DOWNLOADING = auto()
    UNITING_SEGMENTS = auto()
    MAKING_FINAL_VIDEO = auto()
    DONE = auto()


class FilmParser:
    baseUrl: str = "https://hdrezka.ag"
    headers: dict = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0"}

    def __init__(self, film_name: str = None):
        self.__state = ParserState.INIT
        self.film_name: str = film_name
        self.__film_data_list = None
        self.__current_segment: int = 0

    # Установка нового запроса по названию и обновление данных по запросу
    def set_film_name_and_update_data(self, film_name):
        self.__state = ParserState.INIT
        self.film_name = film_name
        self.generate_film_list()
        self.__current_segment = 0

    # Создание загрузочной ссылки
    def __create_download_url(self, base_url: str, seg_num: int) -> str:
        url_template = re.split(r'seg-\d+', base_url)
        url_template.insert(1, f"seg-{seg_num}")
        return ''.join(url_template)

    # Сгенерировать список фильмов по запросу
    def generate_film_list(self):
        searchParams: dict[str, str] = {'do': 'search', 'subaction': 'search', 'q': self.film_name}
        searchURL: str = self.baseUrl + '/search/?' + urllib.parse.urlencode(searchParams)
        mainReq = requests.get(url=searchURL, headers=self.headers)
        mainSoup = BeautifulSoup(mainReq.text, "lxml")
        self.__film_data_list = [{
            "name": card.findAll('a')[-1].text,
            "type": card.find('i').text,
            "other": card.findAll('div')[-1].text,
            "status": card.find('span', 'info').text if card.find('span', 'info') else None,
            "link": card.get('data-url'),
        } for card in mainSoup.findAll("div", "b-content__inline_item")]

    def get_film_list(self) -> list[dict]:
        if self.__film_data_list is None:
            self.generate_film_list()
        return self.__film_data_list

    def set_film_by_index(self, index: int):
        if self.__film_data_list is None:
            self.get_film_list()
        self.__film_data = self.__film_data_list[index]

    def start_download(self, max_part_len: int = 75):
        if self.__film_data is None:
            raise ValueError("Error: You forgot to call set_film_data!")
        if self.film_name is None:
            raise  ValueError("Error: You didn't update film name!")
        self.__state = ParserState.SEARCHING_URL
        driver = webdriver.Firefox()

        driver.minimize_window()  # .maximize_window()
        driver.get(self.__film_data['link'])
        video = WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CSS_SELECTOR,
                                                                         "#oframecdnplayer > pjsdiv:nth-child(8) > "
                                                                         "pjsdiv:nth-child(1) > pjsdiv"))
        video.click()

        while True:
            time.sleep(1)
            try:
                skip_btn = WebDriverWait(driver, 1).until(
                    lambda d: d.find_element(By.CSS_SELECTOR,
                                             "#oframecdnplayer > pjsdiv:nth-child(29) > pjsdiv:nth-child(6) > pjsdiv"))
                if skip_btn.text == "Пропустить":
                    skip_btn.click()
                else:
                    continue
            except:
                # print("adds skipped")
                break

        # self.time: str = WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CSS_SELECTOR, '#oframecdnplayer '
        #                                                                                             '> '
        #                                                                                             'pjsdiv:nth-child(14) > pjsdiv:nth-child(2) > noindex:nth-child(1)')).text

        # print("searching url...")
        download_urls: list[str] = list()
        while not download_urls:
            download_urls = list()
            test = driver.execute_script(
                "var performance = window.performance || "
                "window.mozPerformance || window.msPerformance || "
                "window.webkitPerformance || {}; var network = performance.getEntries() || "
                "{}; return network;"
            )
            for item in test:
                logged_url = field_deep_search(item, "name")[0]
                if logged_url.split(".")[-1] == "ts":
                    download_urls.append(logged_url)
            time.sleep(1)

        driver.quit()

        # self.__state = ParserState.MANAGING_DIRECTORIES
        film_full_name: str = self.__film_data["name"]
        if not os.path.exists("films"):
            os.mkdir("films")
        os.chdir("films")
        if os.path.exists(film_full_name):
            for root, dirs, files in os.walk(film_full_name, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(film_full_name)
        os.mkdir(film_full_name)
        os.chdir(film_full_name)
        if not os.path.exists("segments"):
            os.mkdir("segments")
        os.chdir("segments")

        seg_fn_list = list()
        baseDownloadUrl: str = download_urls[0]
        segment: int = 1
        self.__state = ParserState.DOWNLOADING
        while requests.get((new_url := self.__create_download_url(baseDownloadUrl, segment))).ok:
            self.__current_segment = segment
            seg_file: str = f'{film_full_name}-{segment}'
            download_file(new_url, f"{seg_file}.ts")
            # print(f"downloaded segment is {segment} by url {new_url}")
            subprocess.run(['ffmpeg', '-i', f"{seg_file}.ts", seg_fn := f"{seg_file}.mp4"], capture_output=True)
            seg_fn_list.append(seg_fn)
            os.remove(f"{seg_file}.ts")
            segment += 1

        # max_part_len = 75
        if segment <= max_part_len:
            self.__state = ParserState.MAKING_FINAL_VIDEO
            final_clip = concatenate_videoclips([VideoFileClip(fn) for fn in seg_fn_list])
            os.chdir("..")
            final_clip.write_videofile(f"{film_full_name}-final.mp4", logger=None)
        else:
            # self.__state = ParserState.MAKING_DIRS
            os.chdir("..")
            if not os.path.exists("parts"):
                os.mkdir("parts")
            os.chdir("segments")

            self.__state = ParserState.UNITING_SEGMENTS
            part_fn_list = list()
            for part_num in range(1, (segment // max_part_len) + 2):
                end: int = min(part_num * max_part_len, segment - 1)
                os.chdir("..")
                os.chdir("parts")
                part_fn: str = f"{film_full_name}-part-{part_num}[{(part_num - 1) * max_part_len}-{end - 1}].mp4"
                os.chdir("..")
                os.chdir("segments")
                part_clip = concatenate_videoclips(
                    [VideoFileClip(fn) for fn in seg_fn_list[(part_num - 1) * max_part_len:end]])
                os.chdir("..")
                os.chdir("parts")
                part_clip.write_videofile(part_fn, logger=None)
                os.chdir("..")
                os.chdir("segments")
                part_fn_list.append(part_fn)

            os.chdir("..")
            os.chdir("parts")
            self.__state = ParserState.MAKING_FINAL_VIDEO
            final_clip = concatenate_videoclips([VideoFileClip(fn) for fn in part_fn_list])
            os.chdir("..")
            final_clip.write_videofile(f"{film_full_name}-final.mp4", logger=None)

        self.__state = ParserState.DONE

    def get_state(self):
        return self.__state

    def get_film_data(self) -> dict:
        return dict(self.__film_data)


if __name__ == '__main__':
    fp = FilmParser("Ух ты")
    fp.set_film_by_index(0)
    current_state = fp.get_state()
    x = threading.Thread(target=fp.start_download, args=(50,))
    x.start()
    while fp.get_state() != ParserState.DONE:
        time.sleep(1)
        if fp.get_state() > current_state:
            print((current_state := fp.get_state()).name)
    x.join()
