import hashlib
import logging
import os
import re
import time
from datetime import datetime

import git
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configuration
API_KEY = os.getenv("LASTFM_API_KEY")
USERNAME = os.getenv("LASTFM_USERNAME")
README_FILE = "README.md"
API_URL = "http://ws.audioscrobbler.com/2.0/"
REPO_PATH = os.getenv("REPO_PATH", ".")  # Path to your git repository
UPDATE_INTERVAL = 60  # Check for updates every 60 seconds


def get_current_track():
    params = {
        "method": "user.getrecenttracks",
        "user": USERNAME,
        "api_key": API_KEY,
        "format": "json",
        "limit": 1,
    }
    try:
        response = requests.get(API_URL, params=params)
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
    return f"""
> **Now Playing:** {track['name']} - {track['artist']} [{track['album']}]
> 
> [Last.fm]({track['url']}) | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""


def update_repo(track):
    try:
        repo = git.Repo(REPO_PATH)
        readme_path = os.path.join(REPO_PATH, README_FILE)

        with open(readme_path, "r") as file:
            content = file.read()

        new_block = create_now_playing_block(track)

        # Check if the info block already exists
        pattern = r"(> \*\*Now Playing:\*\*.*\n>.*\n>.*(?:\n>.*)*)"
        if re.search(pattern, content):
            # Replace existing info block
            new_content = re.sub(pattern, new_block.strip(), content)
        else:
            # Add new info block at the end
            new_content = content.rstrip() + "\n\n" + new_block

        # Check if there are any changes
        if new_content == content:
            logging.info("No changes detected. Skipping update.")
            return

        # Write the updated content
        with open(readme_path, "w") as file:
            file.write(new_content)

        # Stage the changes
        repo.git.add(README_FILE)

        # Amend the last commit and update its timestamp
        commit_message = f"Update Now Playing Information\n\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        repo.git.commit("--amend", "-m", commit_message)

        # Force push the amended commit
        repo.git.push("--force")
        logging.info("Repository updated with amended 'Now Playing' information.")
    except git.GitCommandError as e:
        logging.error(f"Git error: {e}")
    except Exception as e:
        logging.error(f"Error updating README: {e}")


def get_track_hash(track):
    if not track:
        return None
    return hashlib.md5(
        f"{track['artist']}:{track['name']}:{track['album']}".encode()
    ).hexdigest()


def main():
    if not API_KEY or not USERNAME:
        logging.error(
            "Last.fm API key or username not set. Please set LASTFM_API_KEY and LASTFM_USERNAME environment variables."
        )
        return

    last_track_hash = None

    while True:
        track = get_current_track()
        if not track:
            logging.error("Failed to get track information.")
            time.sleep(UPDATE_INTERVAL)
            continue

        current_track_hash = get_track_hash(track)

        if current_track_hash != last_track_hash:
            update_repo(track)
            last_track_hash = current_track_hash
        else:
            logging.info("Track hasn't changed. Skipping update.")

        time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    main()
