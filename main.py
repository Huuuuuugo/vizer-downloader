import time
import json
import re
import os

import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options


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
    time.sleep(3)

    print("Browser started.")
    return browser

def request_download_data(episode: dict):
    url = r"https://vizertv.in/includes/ajax/publicFunctions.php"
    payload = {'downloadData': 2, 'id': int(episode["id"])}

    response = requests.post(url, data=payload)

    # check if response status code is valid before proceeding
    if response.status_code != 200:
        message = f"Unexpected status code for '{episode["episode-number"]}. {episode["title"]}': {response.status_code}"
        raise requests.RequestException(message)

    # get dictionary containing the response
    response_json = response.json()

    # get redirect links and subtitle link from response
    for key in response_json:
        entry: dict = response_json[key]
        if "sub" in entry.keys(): 
            orig_audio_redirect = entry["redirector"]
            subtitles = entry["sub"]

        else:
            dub_audio_redirect = entry["redirector"]
    
    return orig_audio_redirect, dub_audio_redirect, subtitles

def request_download_link(redirect_link: str):
    response = requests.get(f"https://vizertv.in/{redirect_link}")
    html = BeautifulSoup(response.content, 'html.parser')

    download_link = re.search(r'window\.location\.href=\".*(mixdrop.+)\"', str(html))
    if download_link:
        download_link = f"https://{download_link.group(1)}?download"
    
    else:
        message = f"Could not find a download on the given redirect link (https://vizertv.in/{redirect_link})."
        raise requests.RequestException(message)
    
    return download_link

def get_episodes_data(browser: uc.Chrome, season: int, url: str):
    # get browser into view
    browser.set_window_size(1200, 600)

    # get web page
    browser.get(url)

    # find the 'choose season' button and click it
    print("Searching for season...")
    select_season_btn = browser.find_element(By.CLASS_NAME, "seasons")
    select_season_btn.click()

    # find all season buttons
    season_btn_list = browser.find_element(By.XPATH, "/html/body/main/div[3]/div/div[3]/div[2]/div[2]").find_elements(By.CLASS_NAME, "item")

    # search for the button for the specified season and click it
    for season_btn in season_btn_list:
        season_number = re.match(r"^([0-9]+)", season_btn.text)
        if season_number:
            season_number = int(season_number.group(1))

        if season_number == season:
            season_btn.click()
            break
    else:
        browser.close()
        message = f"Season '{season}' does not exist on the given url ({url})."
        raise AttributeError(message)

    # get info from all episode from that season and the name of the series
    episode_list = browser.find_element(By.XPATH, "/html/body/main/div[3]/div/div[3]/div[3]").find_elements(By.CSS_SELECTOR, "div.item[data-episode-id]:not(.unreleased)")
    series_name = browser.find_element(By.CSS_SELECTOR, "h2").text
    
    # set up dictionary for storing the informations from that season
    season_dict = {
        "series-name": series_name,
        "season-number": season,
        "episodes": []
    }

    # cycle trhough every episode and store its properties inside 'season_dict'
    for episode in episode_list:
        episode_id = episode.get_dom_attribute("data-episode-id")
        title_string = episode.find_element(By.CLASS_NAME, "tit").text
        episode_number, episode_title = title_string.split('.')
        episode_title = episode_title.strip()
        episode_info = episode.find_element(By.CLASS_NAME, "info").text

        episode_dict = {
            "episode-number": episode_number,
            "title": episode_title,
            "info": episode_info,
            "id": episode_id
        }
        
        season_dict["episodes"].append(episode_dict)
        print(f"Got episode data for '{episode_number}. {episode_title}'.")

    browser.set_window_size(800, 600)
    browser.minimize_window()
        
    # get download links
    for index, episode in enumerate(season_dict["episodes"]):
        # make post request for the download data associated with the current episode 
        print(f"Requesting download data for '{episode["episode-number"]}. {episode["title"]}'.")
        orig_audio_redirect, dub_audio_redirect, subtitles = request_download_data(episode)
        
        # get original audio download link from redirector
        print("Requesting original audio download link.")
        orig_audio_download_link = request_download_link(orig_audio_redirect)
        
        # get dubbed audio download link from redirector
        print("Requesting dubbed audio download link.")
        dub_audio_download_link = request_download_link(dub_audio_redirect)
        
        # save data to season_dict
        download_dict = {
            "original-audio": orig_audio_download_link,
            "dubbed-audio": dub_audio_download_link,
            "subtitles": subtitles
        }

        season_dict["episodes"][index].update({"downloads": download_dict})
        print(f"Got download data for '{episode["episode-number"]}. {episode["title"]}'.")
    
    # save json file
    with open(f"output/{season_dict["series-name"]} S{str(season).zfill(2)}.json", 'w') as file:
        json.dump(season_dict, file, indent=2)
  
    return season_dict


if __name__ == "__main__":
    season = 1
    url = "https://vizertv.in/serie/online/sobrenatural"

    browser = start_browser()

    season_dict = get_episodes_data(browser, season, url)

    browser.close()
    time.sleep(3)