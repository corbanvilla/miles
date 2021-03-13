import re
import subprocess
import json
import requests

from loguru import logger
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from os import environ

from miles_slack.slack_files import download_slack_file, upload_slack_file

BASE_API_URL = environ.get("BASE_API_URL").rstrip('/')
RCLONE_DRIVE = environ.get("RCLONE_DRIVE")
DRIVE_PATH_PREFIX = environ.get("DRIVE_PATH_PREFIX")
DRIVE_OUTPUT_DIR = environ.get("DRIVE_OUTPUT_DIR")
DRIVE_OUTPUT_LINK = environ.get("DRIVE_OUTPUT_LINK")

SLACK_BOT_TOKEN = environ.get("SLACK_BOT_TOKEN")
SLACK_SOCKET_TOKEN = environ.get("SLACK_SOCKET_TOKEN")


app = App(token=SLACK_BOT_TOKEN)

command_filter = re.compile(r'<@.*>(.*)')  # turns '<@U01KMRM2YTG> hello world' to 'hello world'
arg_filter = re.compile(r'\s(.*)')  # turns 'find Thomas Web' into 'Thomas Web'


@app.event("app_mention")
def event_test(say, event, client):
    say("Got it! Gimmie a hot sec....")
    logger.debug(f"Event received: {event}")
    channel = event.get("channel")
    command = command_filter.findall(event.get("text"))[0].strip()
    files = event.get("files")

    if files:
        for file in files:
            # Download Slack File
            image_stream = download_slack_file(file.get("thumb_1024") or file.get("url_private_download"))  # if smaller than 1024x1024

            logger.debug(f"File downloaded!")

            try:
                req = requests.post(
                    url=f'{BASE_API_URL}/predict_label_image/',
                    files={'image': image_stream},
                )

                upload_slack_file(
                    file=req.content,
                    channel=channel,
                    client=client,
                    message="Here you go!"
                )

                # accuracy_scores = [f'Top guesses: {guess} {score}%\n' for guess, score in json.loads(req.headers.get('accuracy_scores'))]
                accuracy_scores = [f'{profile[0][0]} ({profile[0][1]}%)... or {profile[1][0]} ({profile[1][1]}%)... or {profile[2][0]} ({profile[2][1]}%)\n' for profile in json.loads(req.headers.get('accuracy_scores')).values()]

                say(f"Accuracy scores: {*accuracy_scores,}")

            except requests.ConnectionError as e:
                logger.error(f"Unable to reach backend.... {e}")
                say("Internal error... unable to reach backend: miles_api")

    elif command.split(" ")[0] == "find":
        name = command.split(" ", maxsplit=1)[-1]  # Take everything past the first word

        try:
            payload = {
                "search_string": name,
                "rclone_drive": RCLONE_DRIVE,
                "path": DRIVE_PATH_PREFIX,
                "output_dir": DRIVE_OUTPUT_DIR,
            }

            req = requests.post(
                url=f'{BASE_API_URL}/find_person/',
                data=json.dumps(payload)
            )

            say(f"Uploading photos of: {json.loads(req.text).get('profile_name')} to {RCLONE_DRIVE}:{DRIVE_PATH_PREFIX}/{DRIVE_OUTPUT_DIR}")
            say(f"{DRIVE_OUTPUT_LINK}")

        except requests.ConnectionError as e:
            logger.error(f"Unable to reach backend.... {e}")
            say("Internal error... unable to reach backend: miles_api")


def main():
    SocketModeHandler(app, SLACK_SOCKET_TOKEN).start()
