import re
import face_recognition
import subprocess
import json

from loguru import logger
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from miles_predict.helpers.slack_files import download_slack_file, upload_slack_file
from miles_predict.helpers.load_model import faces_to_images, images_index
from miles_predict.predict import find_known_faces
from miles_predict.resources.default_configs import (
    SLACK_SOCKET_TOKEN,
    SLACK_BOT_TOKEN
)

rclone_drive = "2021_gdrive"
main_dir = "01- Photos"
people_dir = "Face Recognition"

app = App(token=SLACK_BOT_TOKEN)

command_filter = re.compile(r'<@.*>(.*)')  # turns '<@U01KMRM2YTG> hello world' to 'hello world'


def name_filter(name):
    return re.compile(r'find (.*)').findall(name)[0].replace(" ", "").lower()  # turns 'find Thomas Web' into 'thomasweb


@logger.catch
@app.event("app_mention")
def event_test(say, event, client):
    say("Got it! Gimmie a hot sec....")
    channel = event.get("channel")
    command = command_filter.findall(event.get("text"))[0].strip()
    files = event.get("files")

    if files:
        for file in files:
            # Download Slack File
            image_stream = download_slack_file(file["url_private_download"])

            faces_image_stream = find_known_faces(image_stream)

            upload_slack_file(
                file=faces_image_stream,
                channel=channel,
                client=client,
                message="Here you go!"
            )
    elif command.split(" ")[0] == "find":
        name = name_filter(command)

        # try and find the corresponding person
        name_search = re.compile(fr'.*{name}.*', re.IGNORECASE)
        if any((match := name_search.match(x)) for x in faces_to_images.keys()):
            match = match[0]  # Grab the name from the object
            logger.debug(f'Found name: {match}')
            say(f"Found {match} in database! Looking photos with them.....")
            photos = [images_index[photo_hash] for photo_hash in json.loads(faces_to_images[match])]  # Turn hashes to paths in google drive

            logger.debug(f'Found {len(photos)} photos!')
            # Make a folder for our person
            subprocess.run(['rclone', 'mkdir', fr'{rclone_drive}:/{main_dir}/{people_dir}/{match}'])
            say(f"Photos will start appearing in: {main_dir}/{people_dir}/{match}.....")

            # Copy the photos we have for them
            for full_photo_path in photos:
                photo_name = full_photo_path.rsplit('/', maxsplit=1)[-1]
                logger.debug(f"Coppied {photo_name}")
                subprocess.run(
                    ['rclone', 'copyto',
                     fr'{rclone_drive}:/{main_dir}/{full_photo_path}',  # Source
                     fr'{rclone_drive}:/{main_dir}/{people_dir}/{match}/{photo_name}']  # Destination
                )

            logger.debug("Done!")
            say("Done!")

        else:
            say(f"Could not find: {name}... make sure it's spelled right!")


def main():
    SocketModeHandler(app, SLACK_SOCKET_TOKEN).start()
