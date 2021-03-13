import requests

from os import environ
from io import BytesIO
from slack_sdk.errors import SlackApiError
from loguru import logger

SLACK_BOT_TOKEN = environ.get("SLACK_BOT_TOKEN")


def download_slack_file(url):
    """
    Grab file from Slack using bot token

    There's not a BOLT SDK implementation to download files

    return: Image file-object
    """
    try:
        logger.info(f"Downloading file: {url}")
        # Image binary data needs to be a binary stream (like a file-object)
        return BytesIO(requests.get(url, headers={'Authorization': f'Bearer {SLACK_BOT_TOKEN}'}).content)
    except Exception as e:
        print(f"Unable to grab file: {e}")
        return None


def upload_slack_file(file, channel, client, message):
    """
    Uploads files to Slack using BOLT SDK

    https://api.slack.com/methods/files.upload/code
    """
    try:
        # Call the files.upload method using the WebClient
        # Uploading files requires the `files:write` scope
        result = client.files_upload(
            channels=channel,
            initial_comment=message,
            file=file,
            filetype="jpg"
        )
        # Log the result
        logger.info(result)

    except SlackApiError as e:
        logger.error("Error uploading file: {}".format(e))
