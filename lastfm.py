import hashlib
import logging
import os
import re
import time
from datetime import datetime

import git
import pytz
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configuration
API_KEY = os.getenv("LASTFM_API_KEY")
USERNAME = os.getenv("LASTFM_USERNAME")
README_FILE = "README.md"
API_URL = "http://ws.audioscrobbler.com/2.0/"
REPO_PATH = os.getenv("REPO_PATH", ".")
UPDATE_INTERVAL = 60  # Check for updates every 60 seconds

# Set up a session with retries
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
session.mount("http://", HTTPAdapter(max_retries=retries))
session.mount("https://", HTTPAdapter(max_retries=retries))

# Indian timezone
indian_tz = pytz.timezone("Asia/Kolkata")


def get_current_track():
    params = {
        "method": "user.getrecenttracks",
        "user": USERNAME,
        "api_key": API_KEY,
        "format": "json",
        "limit": 1,
    }
    try:
        response = session.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        track = data["recenttracks"]["track"][0]
        return {
            "artist": track["artist"]["#text"],
            "name": track["name"],
            "album": track["album"]["#text"],
            "url": track["url"],
        }
    except requests.RequestException as e:
        logging.error(f"Error fetching data from Last.fm: {e}")
        return None


def create_now_playing_block(track):
    current_time = datetime.now(indian_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    return f"""> **Now Playing:** {track['name']} - {track['artist']} [{track['album']}]
> 
> [Last.fm]({track['url']}) | Updated: {current_time}"""


def update_repo(track, repo, readme_path):
    try:
        with open(readme_path, "r") as file:
            content = file.read()

        new_block = create_now_playing_block(track)
        pattern = r"(> \*\*Now Playing:\*\*.*\n>.*\n>.*(?:\n>.*)*)"

        if re.search(pattern, content):
            new_content = re.sub(pattern, new_block.strip(), content)
        else:
            new_content = content.rstrip() + "\n\n" + new_block

        if new_content == content:
            logging.info("No changes detected. Skipping update.")
            return

        with open(readme_path, "w") as file:
            file.write(new_content)

        repo.git.add(README_FILE)
        commit_message = f"Update Now Playing Information\n\nLast updated: {datetime.now(indian_tz).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        repo.git.commit("--amend", "-m", commit_message)
        repo.git.push("--force")
        logging.info("Repository updated with amended 'Now Playing' information.")
    except git.GitCommandError as e:
        logging.error(f"Git error: {e}")
    except Exception as e:
        logging.error(f"Error updating README: {e}")


def get_track_hash(track):
    return (
        hashlib.md5(
            f"{track['artist']}:{track['name']}:{track['album']}".encode()
        ).hexdigest()
        if track
        else None
    )


def main():
    if not API_KEY or not USERNAME:
        logging.error(
            "Last.fm API key or username not set. Please set LASTFM_API_KEY and LASTFM_USERNAME environment variables."
        )
        return

    repo = git.Repo(REPO_PATH)
    readme_path = os.path.join(REPO_PATH, README_FILE)
    last_track_hash = None

    while True:
        track = get_current_track()
        if not track:
            logging.error("Failed to get track information.")
        else:
            current_track_hash = get_track_hash(track)
            if current_track_hash != last_track_hash:
                update_repo(track, repo, readme_path)
                last_track_hash = current_track_hash
            else:
                logging.info("Track hasn't changed. Skipping update.")

        time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    main()
