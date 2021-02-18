from os import environ
from loguru import logger
from redis import Redis

# Redis Conn
redis_host = environ.get("REDIS_HOST")
logger.debug(f"Storing to redis at: {redis_host}")

r = Redis(redis_host)
