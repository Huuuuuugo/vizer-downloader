import threading
import warnings
import argparse
import random
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

from downloader import Download


# rewrites the __del__ method to fix an oversight that throws an unnecessary warning every time Crhome.quit() is called
class FixedChrome(uc.Chrome):
    def __del__(self):
        try:
            self.quit()
        except: #noqa
            pass

def start_browser():
    try:
        print("Starting browser...")
        browser = None

        # set options
        options = uc.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")

        # load uBlock
        extension_dir = os.path.join(os.getcwd(), "uBlock")
        options.add_argument(f"--load-extension={extension_dir}")

        # start browser
        browser = FixedChrome(options=options)
        browser.set_window_size(800, 600)
        browser.implicitly_wait(15)
        browser.minimize_window()

        # set custom user agent
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
        browser.execute_cdp_cmd('Network.setUserAgentOverride', {'userAgent': user_agent})

        # wait for uBlock to load
        time.sleep(5)

        print("Browser started.")
        return browser

    except KeyboardInterrupt:
        print("Closing browser...")
        if browser is not None:
            browser.quit()

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
    orig_audio_redirect = None 
    dub_audio_redirect = None
    subtitles = None
    for key in response_json:
        entry: dict = response_json[key]
        if "sub" in entry.keys(): 
            orig_audio_redirect = entry["redirector"]
            subtitles = entry["sub"]

        else:
            dub_audio_redirect = entry["redirector"]
    
    return orig_audio_redirect, dub_audio_redirect, subtitles

def request_download_link(redirect_link: str):
    if redirect_link is None:
        return None
    
    response = requests.get(f"https://vizertv.in/{redirect_link}")
    html = BeautifulSoup(response.content, 'html.parser')

    download_link = re.search(r'window\.location\.href=\".*(mixdrop.+)\"', str(html))
    if download_link:
        download_link = f"https://{download_link.group(1)}?download"
    
    else:
        message = f"Could not find a download on the given redirect link (https://vizertv.in/{redirect_link})."
        raise requests.RequestException(message)
    
    return download_link

def get_download_link_from_mixdrop(browser: uc.Chrome, url: str):
    if url is None:
        return None
    
    # bring window into view
    browser.set_window_size(800, 600)

    # get web page
    browser.get(url)

    # click button
    download_btn = browser.find_element(By.CLASS_NAME, "download-btn")
    time.sleep(1+random.random()*1)
    download_btn.click()

    # get download link
    download_link = None
    while download_link is None:
        download_link = browser.find_element(By.CLASS_NAME, "download-btn").get_dom_attribute("href")
        time.sleep(0.5)
    
    return download_link

def get_episodes_data(url: str, season: int):
    try:
        # get browser into view
        browser = None
        browser = start_browser()
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
            episode_number, episode_title = title_string.split('.', 1)
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

        browser.quit()
        browser = None
            
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

    except KeyboardInterrupt:
        pass

    finally:
        if browser is not None:
            browser.quit()

def download_all(json_path: str, output_path: str, download_key: str, extension: str, start_from: int = 1, stop_at: int | None = None, max_downloads: int = 3):
    # read json data
    with open(json_path, 'r') as file:
        season_dict = json.load(file)
    
    # get output path
    output_path = f"{output_path.replace('\\', '/')}/{season_dict["series-name"]}/Temporada {season_dict["season-number"]}"

    if not os.path.isdir(output_path):
        os.makedirs(output_path)

    # start downloading
    try:
        # start browser instance
        browser = None
        browser = start_browser()
        if browser is None:
            return

        # creates a thread for showing downloads progress
        def show_progress_thread():
            while True:
                Download.show_all_progress()
                time.sleep(0.1)
                
        threading.Thread(target=show_progress_thread, daemon=True).start()

        # cycle through every episode on the json
        for episode in season_dict["episodes"]:
            # skip episode from before 'start_from'
            if int(episode["episode-number"]) < start_from:
                continue
            
            # break the loop at 'stop_at' episode
            elif stop_at is not None and int(episode["episode-number"]) > stop_at:
                break

            # waits if there's at least 3 currently active downloads
            while Download.get_running_count() >= max_downloads:
                time.sleep(0.1)
            
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
            if "mixdrop" in url:
                download_link = get_download_link_from_mixdrop(browser, url)

            else:
                download_link = url

            # start download
            if download_link is not None:
                # filter warnnings to avoid breaking the progress printing
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    Download(download_link, f"{output_path}/{file_name}").start()
        
        browser.quit()
        browser = None
        
        # wait for the last downloads to finish
        Download.wait_downloads(False)
        time.sleep(0.5) # wait for one last update on the show_progress_thread before finishing
    
    except KeyboardInterrupt:
        pass
    
    finally:
        # close browser instance
        if browser is not None:
            browser.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(dest='action', help="available commands:")
    
    # info args
    info_args = subparser.add_parser(
        'info',
        help="gathers info about all episodes from a chosen season, including name, number and download links"
    )
    info_args.add_argument('-url', '--url', type=str, required=True, help="url to the series page")
    info_args.add_argument('-s', '--season', type=int, required=True, help="number of the desired season")

    # download args
    download_args = subparser.add_parser(
        'download',
        help="downloads files based on provided data"
    )
    download_args.add_argument('-i', '--input', type=str, required=True, help="path to the json file containing the download data")
    download_args.add_argument('-k', '--key', required=True, choices=['dub', 'eng', 'sub'], help="key to the download link: 'dub' for dubbed, 'eng' for english, 'sub' for subtitles")
    download_args.add_argument('-o', '--output', default=(os.path.curdir).replace('\\', '/'), help="path where the files will be saved")
    download_args.add_argument('--start-from', type=int, default=1, help="number of the episode to start downloading from")
    download_args.add_argument('--stop-at', type=int, default=None, help="number of the episode to stop downloading at")
    download_args.add_argument('--max-downloads', type=int, default=3, help="number of maximum concurrent downloads")


    args = parser.parse_args()

    if args.action is None:
        parser.print_help()

    elif args.action == 'info':
        get_episodes_data(args.url, args.season)

    elif args.action == 'download':
        match args.key:
            case 'dub':
                download_key = 'dubbed-audio'
                extension = '.mp4'

            case 'eng':
                download_key = 'original-audio'
                extension = '.mp4'
            
            case 'sub':
                download_key = 'subtitles'
                extension = '.srt'

        download_all(args.input, args.output, download_key, extension, args.start_from, args.stop_at, args.max_downloads)