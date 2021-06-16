import face_recognition
import re
import json
import msgpack
import msgpack_numpy as m
import numpy as np
import time
m.patch()

from loguru import logger
from glob import iglob
from PIL import Image, ImageDraw
from os import environ

from redis import Redis

training_regex = environ.get("TRAINING_REGEX")
redis_host = environ.get("REDIS_HOST")

logger.debug(f"Using regex: {training_regex}")
logger.debug(f"Storing to redis at: {redis_host}")

r = Redis(redis_host)

training_files = iglob(training_regex)
name_regex = re.compile(r"_(.*?)_01\.")

# Grab a couple files to process
# img_names = [next(training_files) for _ in range(0, 20)]
img_names = [img for img in training_files]

try:
    logger.debug(f"{len(img_names)} images loaded: {img_names[:2]}.... {img_names[-1]}")
except IndexError:  # Less than 2 images... something is up
    logger.debug(f"Images loaded: {img_names}")

# Loop through creating nice profile names
profiles = []
for profile in img_names:
    filename = profile.rsplit('/', maxsplit=1)[1]
    lastname, firstname = name_regex.findall(filename)[-1].rsplit('_', maxsplit=1)
    lastname = lastname.title()
    firstname = firstname.title()
    profiles.append(firstname + lastname)

# Load all images into memory
images = [face_recognition.load_image_file(name) for name in img_names]

# Find all our faces using the GPU-accelerated CNN model
logger.debug("Finding faces....")
start_time = time.time()
face_locations = face_recognition.batch_face_locations(images, number_of_times_to_upsample=0)  # Load all face locations
end_time = time.time()
logger.debug(f"Found {len(face_locations)} faces in {end_time - start_time}")

# Make sure that we only have 1 face / picture
assert len(face_locations) == len(images)

# Grab face encodings for each location
known_face_encodings = [face_recognition.face_encodings(image, face_location)[0] for image, face_location in zip(images, face_locations)]

# Throw our encodings into Redis
packed_known_encodings = m.packb(known_face_encodings)

r.set('known_face_encodings', packed_known_encodings)
r.set('profiles', json.dumps(profiles))
