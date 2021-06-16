from os import environ

REDIS_HOST = environ.get("REDIS_HOST")

REDIS_IMAGES_INDEX = environ.get("REDIS_IMAGES_INDEX") or "images_index"

REDIS_KNOWN_FACE_ENCODINGS = environ.get("REDIS_KNOWN_FACE_ENCODINGS") or "known_face_encodings"
REDIS_ALL_FACE_ENCODINGS = environ.get("REDIS_ALL_FACE_ENCODINGS") or "all_face_encodings"
REDIS_PROFILES = environ.get("REDIS_PROFILES") or "profiles"

REDIS_FACES_TO_IMAGES = environ.get("REDIS_FACES_TO_IMAGES") or "faces_to_images"
REDIS_IMAGES_TO_FACES = environ.get("REDIS_IMAGES_TO_FACES") or "images_to_faces"

REDIS_DOWNLOADED_IMAGES = environ.get("REDIS_DOWNLOADED_IMAGES") or "downloaded_images"
REDIS_SKIPPED_IMAGES = environ.get("REDIS_SKIPPED_IMAGES") or "skipped_images"
REDIS_SCANNED_IMAGES = environ.get("REDIS_SCANNED_IMAGES") or "scanned_images"
REDIS_PROCESSED_IMAGES = environ.get("REDIS_PROCESSED_IMAGES") or "processed_images"
