from os import environ

# Slack token config
SLACK_SOCKET_TOKEN = environ.get("SLACK_SOCKET_TOKEN")  # starts w/ xapp
SLACK_BOT_TOKEN = environ.get("SLACK_BOT_TOKEN")  # starts w/ xoxb

REDIS_HOST = environ.get("REDIS_HOST")
