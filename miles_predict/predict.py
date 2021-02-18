import face_recognition
import numpy as np

from io import BytesIO
from PIL import Image, ImageDraw
from loguru import logger

from miles_predict.helpers.load_model import profiles, known_face_encodings


@logger.catch
def find_known_faces(stream_image):
    """
    Find known faces in an image

    return: Image file-object with faces named
    """

    # Load image
    image = face_recognition.load_image_file(stream_image)

    # Create an image to draw on
    overlay_image = Image.fromarray(image)
    draw = ImageDraw.Draw(overlay_image)

    # Find all the faces and face encodings in the unknown image
    # face_locations = face_recognition.face_locations(image, model="cnn")
    face_locations = face_recognition.face_locations(image, model="hog")
    face_encodings = face_recognition.face_encodings(image, face_locations)

    # match_face_encodings(face_locations, face_encodings)
    match_face_encodings(face_locations, face_encodings, draw)

    del draw

    # Shrink our image
    # overlay_image.thumbnail((1024, 1024), Image.ANTIALIAS)

    # Save it into a bytes stream
    output_image_stream = BytesIO()
    overlay_image.save(output_image_stream, format='JPEG')

    return output_image_stream.getvalue()


def match_face_encodings(face_locations, face_encodings, draw):
    """
    Matches image face encodings with known
    """

    # Loop through faces
    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):

        # See if the face is a match for the known face(s)
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)

        # Use the known face with the smallest distance to the new face
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            name = profiles[best_match_index]
        else:
            name = "Unknown"

        label_face(draw, name, top, right, left, bottom)


def label_face(draw, label_name, top, right, left, bottom):
    # Draw a box around the face using the Pillow module
    draw.rectangle(((left, top), (right, bottom)), outline=(0, 0, 255))

    # Draw a label with a name below the face
    text_width, text_height = draw.textsize(label_name)
    draw.rectangle(((left, bottom - text_height - 10), (right, bottom)), fill=(0, 0, 255), outline=(0, 0, 255))
    draw.text((left + 6, bottom - text_height - 5), label_name, fill=(255, 255, 255, 255))
