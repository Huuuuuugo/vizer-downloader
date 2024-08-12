import json
import re

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options


def get_episodes_info(season: int, url: str, headless: bool = True):
    # set options
    options = Options()
    if headless:
        options.add_argument("--headless") # hide browser window

    # start browser inside a context manager
    print("Starting browser...")
    with webdriver.Firefox(options=options) as browser:
        # wait for page to load
        browser.implicitly_wait(15)

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
            season_number = re.match(r"^[0-9]+", season_btn.text).group()
            if int(season_number) == season:
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
            episode_rating = episode.find_element(By.CLASS_NAME, "info").text

            episode_dict = {
                "episode-number": episode_number,
                "title": episode_title,
                "rating": episode_rating,
                "id": episode_id
            }
            
            season_dict["episodes"].append(episode_dict)
            print(f"Got episode data for '{episode_number}. {episode_title}'.")
        
    # get download links
    for index, episode in enumerate(season_dict["episodes"]):
        # make post request for the download data associated with the current episode 
        print(f"Requesting download data for '{episode["episode-number"]}. {episode["title"]}'.")
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
        
        # get original audio download link from redirector
        print("Requesting original audio download link.")
        response = requests.get(f"https://vizertv.in/{orig_audio_redirect}")
        html = BeautifulSoup(response.content, 'html.parser')

        orig_audio_download_link = re.search(r'window\.location\.href=\".*(mixdrop.+)\"', str(html))
        if orig_audio_download_link:
            orig_audio_download_link = f"https://{orig_audio_download_link.group(1)}?download"
        
        # get dubbed audio download link from redirector
        print("Requesting dubbed audio download link.")
        response = requests.get(f"https://vizertv.in/{dub_audio_redirect}")
        html = BeautifulSoup(response.content, 'html.parser')

        dub_audio_download_link = re.search(r'window\.location\.href=\".*(mixdrop.+)\"', str(html))
        if dub_audio_download_link:
            dub_audio_download_link = f"https://{dub_audio_download_link.group(1)}?download"
        
        # save data to season_dict
        download_dict = {
            "original-audio": orig_audio_download_link,
            "dubbed-audio": dub_audio_download_link,
            "subtitles": subtitles
        }

        season_dict["episodes"][index].update({"downloads": download_dict})
        print(f"Got download data for '{episode["episode-number"]}. {episode["title"]}'.")
  
    return season_dict


if __name__ == "__main__":
    season = 2
    url = "https://vizertv.in/serie/online/doctor-who"
    season_2 = get_episodes_info(season, url, headless=True)

    with open("output/doctor-who-s02.json", 'w') as file:
        json.dump(season_2, file, indent=2)
