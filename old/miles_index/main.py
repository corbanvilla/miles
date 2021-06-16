import subprocess
import os
import shutil
import json
import magic

from loguru import logger

from miles_index.redis import r
from miles_index.predict import batch_process_faces

# Redis settings
scanned_images_index = "scanned_images_index"
image_index = "images_index"
skipped_images = "skipped_images"

images_to_faces = "images_to_faces"
faces_to_images = "faces_to_images"

batch_size = 20
rclone_drive = "2021_gdrive"
temp_folder = "./temp"
main_dir = "01- Photos"

# Create mime type object
mime = magic.Magic(mime=True)


@logger.catch
def update_image_index():
    """
    Grabs all image metadata from Google drive

    Pushes it to a Redis DB
    """

    logger.debug(f"Fetching photos from {rclone_drive}")
    drive_files = json.loads(subprocess.run(['rclone', 'lsjson', f'{rclone_drive}:/{main_dir}', '--files-only', '--hash', '--no-modtime', '--recursive'], stdout=subprocess.PIPE).stdout)

    images_processed = 0
    for file in drive_files:
        if (file.get("MimeType") == "image/jpeg"):
            # Logging / stats
            images_processed += 1
            logger.debug(f"{images_processed} images processed...") if images_processed % 100 == 0 else ()  # Log increments of 100

            # Grab metadata
            file_hash = file.get('Hashes').get('MD5')
            file_path = file.get('Path')

            # Store data on our image in Redis
            r.hset(image_index, file_hash, file_path)

    logger.debug(f'Done indexing! {images_processed} images indexed.')


@logger.catch
def scan_image_index():
    """
    Downloads images from our index, scans them
    adds mapped faces to Redis
    """

    images = r.hgetall(image_index)
    all_images = len(images)

    # Remove processed and skipped images
    [images.pop(seen_image, None) for seen_image in r.hgetall(images_to_faces).keys()]
    [images.pop(skipped_image, None) for skipped_image in r.hgetall(skipped_images).keys()]
    new_images = len(images)

    logger.info(f"Already processed {all_images - new_images}...")

    images_count = r.hlen(image_index)
    images_processed = 0

    batch = {}
    for image_hash, image_name in [(k.decode('utf-8'), v.decode('utf-8')) for k, v in images.items()]:
        # logger.debug(f"downloading: {rclone_drive}:/01- Photos/Illustrated Photo Pictures/{image_name}")
        download = subprocess.run(['rclone', 'copy', fr'{rclone_drive}:/{main_dir}/{image_name}', temp_folder]).returncode
        filename = image_name.rsplit('/')[-1]

        # Double check we downloaded correctly
        if download != 0:
            logger.error(f'Skipped image: {image_name}! Unable to download....')
            r.hset(skipped_images, image_hash, "unable to download")
            continue

        # Double check file type
        mime_type = mime.from_file(f'{temp_folder}/{filename}')
        if mime_type != "image/jpeg":
            os.remove(f'{temp_folder}/{filename}')
            logger.error(f'Skipped image: {filename} with MimeType: {mime_type}')
            r.hset(skipped_images, image_hash, mime_type)
            continue

        images_processed += 1

        batch[f"{temp_folder}/{filename}"] = image_hash  # Keep track of the image hashes we're currently using
        if images_processed % batch_size == 0 or images_processed == images_count:
            # Logging / stats
            logger.debug(f"{images_processed} images downloaded... processing batch")

            # Scan images
            batch_faces = batch_process_faces(batch)

            # Set image references in Redis
            [r.hset(images_to_faces, img_hash, json.dumps(img_faces)) for img_hash, img_faces in batch_faces.items()]
            [r.hset(faces_to_images, img_face, json.dumps(json.loads(r.hget(faces_to_images, img_face) or '[]') + [img_hash])) for img_hash, img_faces in batch_faces.items() for img_face in img_faces]

            # Remove / Create new temp dir
            shutil.rmtree("temp/")
            os.mkdir("temp/")

            # Clear out our batch / start anew
            batch = {}


def main():
    # update_image_index()
    scan_image_index()

# if __name__ == "__main__":
#     update_image_index()
#     scan_image_index()
