import pickle
import json

from loguru import logger

from miles_shared.redis import r
from miles_shared.resources.default_configs import (
    REDIS_FACES_TO_IMAGES,
    REDIS_IMAGES_TO_FACES,
    REDIS_KNOWN_FACE_ENCODINGS,
    REDIS_PROFILES
)

# # Load face encodings into a numpy array
# known_face_encodings = pickle.loads(r.get(REDIS_KNOWN_FACE_ENCODINGS))
#
# # Load all face encodings
# all_face_encodings = ""
#
# # Load profile names
# profiles = json.loads(r.get(REDIS_PROFILES))
#
# # Pull our image index and faces index
# faces_to_images = {k.decode('utf-8'): v.decode('utf-8') for k, v in r.hgetall(REDIS_FACES_TO_IMAGES).items()}
# images_index = {k.decode('utf-8'): v.decode('utf-8') for k, v in r.hgetall(REDIS_IMAGES_TO_FACES).items()}
#
# logger.debug(f"Successfully loaded all datasources")
