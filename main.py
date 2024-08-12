import json
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options


def get_episodes_info(season: int, url: str, headless: bool = True):
    # set options
    options = Options()
    if headless:
        options.add_argument("--headless") # hide browser window

    # start browser inside a context manager
    with webdriver.Firefox(options=options) as browser:
        # wait for page to load
        browser.implicitly_wait(15)

        # get web page
        browser.get(url)

        # find the 'choose season' button and click it
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
        
    return season_dict


if __name__ == "__main__":
    season = 2
    url = "https://vizertv.in/serie/online/doctor-who"
    season_2 = get_episodes_info(season, url, headless=False)

    with open("output/doctor-who-s02.json", 'w') as file:
        json.dump(season_2, file, indent=2)
