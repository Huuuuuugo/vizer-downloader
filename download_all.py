import threading
import random
import json
import time
import os
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.options import Options

import undetected_chromedriver as uc

from downloader import Download

def start_browser():
    print("Starting browser...")
    # set options
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # load uBlock
    extension_dir = os.path.join(os.getcwd(), "uBlock")
    options.add_argument(f"--load-extension={extension_dir}")

    browser = uc.Chrome(options=options)
    browser.set_window_size(800, 600)
    browser.implicitly_wait(15)
    browser.minimize_window()

    # wait for uBlock to load
    time.sleep(5)

    print("Browser started.")
    return browser

def get_download_link_from_mixdrop(browser: uc.Chrome, url: str):
    # bring window into view
    browser.set_window_size(800, 600)

    # get web page
    browser.get(url)

    # click button
    download_btn = browser.find_element(By.CLASS_NAME, "download-btn")
    time.sleep(1+random.random()*2)
    download_btn.click()

    # get download link
    download_link = None
    while download_link is None:
        download_link = browser.find_element(By.CLASS_NAME, "download-btn").get_dom_attribute("href")
        time.sleep(0.5)
    
    browser.minimize_window()

    return download_link

if __name__ == "__main__":
    # read json data
    with open("output/Doctor Who S02.json", 'r') as file:
        season_dict = json.load(file)
    
    # get output path
    base_output_path = r"C:\Users\hugom\Videos\Filmes"

    output_path = f"{base_output_path.replace('\\', '/')}/{season_dict["series-name"]}/Temporada {season_dict["season-number"]}"

    if not os.path.isdir(output_path):
        os.makedirs(output_path)

    # start browser instance
    browser = start_browser()

    # start downloading
    def download_all(browser: uc.Chrome, download_key: str, extension: str, start_from: int = 1):
        try:
            for episode in season_dict["episodes"]:
                # skip episode from before 'start_from'
                if int(episode["episode-number"]) < start_from:
                    continue

                # waits if there's at least 3 currently active downloads
                while Download.get_running_count() >= 3:
                    Download.wait_downloads()
                
                # get episode rating
                rating = re.findall(r"([0-9]{1,2}\.[0-9]{1,2})", episode["info"])
                if rating:
                    rating = rating[0]

                else:
                    rating = "?"

                # get download url
                url = episode["downloads"][download_key]

                # get file name
                file_name = f"{episode["episode-number"]}. {episode["title"]} ({rating}){extension}"
                
                # get download link
                download_link = get_download_link_from_mixdrop(browser, url)

                # start download
                Download(download_link, f"{output_path}/{file_name}").start()

        finally:
            Download.stop_all()
    
    download_all(browser, "dubbed-audio",".mp4", 7)
    
    # close browser instance
    browser.close()
    time.sleep(3)
