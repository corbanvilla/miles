from redis import Redis
from loguru import logger

from miles_shared.resources.default_configs import (
    REDIS_HOST
)

logger.debug(f"Loading from redis at: {REDIS_HOST}")

redis_args = [REDIS_HOST]
if ":" in REDIS_HOST:
    redis_args = REDIS_HOST.split(':')

r = Redis(*redis_args)
