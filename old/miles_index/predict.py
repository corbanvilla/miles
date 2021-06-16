import face_recognition
import numpy as np

from loguru import logger

from miles_index.helpers.load_model import profiles, known_face_encodings


@logger.catch
def batch_process_faces(image_batch):

    # Load our images into memory, find faces
    logger.debug("Loading faces into memory...")
    images = [face_recognition.load_image_file(img) for img in image_batch]

    # Load all face locations
    logger.debug(f"Batch identify faces....")  # apparently the batch_face_locations method requires the same dimensions, hence:
    face_locations = [face_recognition.face_locations(image, number_of_times_to_upsample=0, model='cnn') for image in images]

    # Encode all found faces
    logger.debug(f"Encoding faces....")
    all_face_encodings = [face_recognition.face_encodings(image, faces) for image, faces in zip(images, face_locations)]

    # Loop through all encodings, find recognized faces
    results = {}
    for image_hash, image_face_encodings in zip(image_batch.values(), all_face_encodings):

        # For every face in the photo
        faces = []
        for face_encoding in image_face_encodings:

            # Find known faces
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding)

            # Use the known face with the smallest distance to the new face
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                name = profiles[best_match_index]
            else:
                name = "Unknown"

            faces.append(name)

        results[image_hash] = faces

    return results
