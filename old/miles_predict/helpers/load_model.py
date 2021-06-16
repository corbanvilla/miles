import msgpack
import msgpack_numpy as m
import numpy as np
import json
m.patch()

from redis import Redis
from os import environ
from loguru import logger

from miles_predict.resources.default_configs import (
    REDIS_HOST
)

faces_to_images_name = "faces_to_images"
images_index_name = "images_index"

logger.debug(f"Loading from redis at: {REDIS_HOST}")

r = Redis(REDIS_HOST)

known_face_encodings = m.unpackb(r.get('known_face_encodings'))
profiles = json.loads(r.get('profiles'))

# Pull our image index and faces index
faces_to_images = {k.decode('utf-8'): v.decode('utf-8') for k, v in r.hgetall(faces_to_images_name).items()}
images_index = {k.decode('utf-8'): v.decode('utf-8') for k, v in r.hgetall(images_index_name).items()}
