import json
import subprocess
import magic
import os
import pickle
import re
import numpy as np
from sklearn.metrics import pairwise
import asyncio
import requests

from numpy.linalg import norm
from redis import Redis
from fuzzywuzzy import process as fz_process
from io import BytesIO
from PIL import Image, ImageDraw
from loguru import logger
from fastapi import FastAPI
from fastapi import BackgroundTasks, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, validator
from typing import Optional, List
from base64 import b64encode

REDIS_HOST = os.environ.get('REDIS_HOST')
redis_args = [REDIS_HOST]
if ":" in REDIS_HOST:
    redis_args = REDIS_HOST.split(':')

r = Redis(*redis_args)

version = os.environ.get('version') or '10'

app = FastAPI()

mime = magic.Magic(mime=True)

profiles = pickle.loads(r.get('known_encodings'))


#################################
#        Compare Faces          #
#################################


def compare_faces(f1, f2):
    def normalize(embedding):
        embedding_norm = norm(embedding)
        normed_embedding = embedding / embedding_norm
        return normed_embedding

    f1 = normalize(f1)
    f2 = normalize(f2)

    return (1. + np.dot(f1, f2)) / 2


def find_closest_match(profiles, f1):
    dists = np.array([compare_faces(profile, f1) for profile in profiles.values()])

    closest_match = np.argmax(dists)

    return list(profiles)[closest_match]


#################################
#         Images Index          #
#################################


class IndexDriveInfo(BaseModel):
    rclone_drive: str
    path: str
    redis_images_index: Optional[str] = f"images_index_{version}"

    @validator('path')
    def no_leading_trailing_slash(cls, v):
        return v.strip('/')


@app.post('/update_image_index/')
async def index_drive(drive_info: IndexDriveInfo, background_tasks: BackgroundTasks):
    background_tasks.add_task(index_drive_process, drive_info)
    return {'message': f"Indexing path: {drive_info.rclone_drive}:{drive_info.path}..."}


def index_drive_process(drive_info: IndexDriveInfo):
    """
    Grabs all image metadata from Google drive

    Pushes it to a Redis DB
    """

    logger.debug(f"Fetching photos from {drive_info.rclone_drive}")
    drive_files = json.loads(subprocess.run(['rclone', 'lsjson', f'{drive_info.rclone_drive}:/{drive_info.path}', '--files-only', '--hash', '--no-modtime', '--recursive'], stdout=subprocess.PIPE).stdout)

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
            r.hset(drive_info.redis_images_index, file_hash, file_path)

    logger.debug(f'Done indexing! {images_processed} images indexed.')


#################################
#        Download Images        #
#################################

class DownloadDriveInfo(BaseModel):
    rclone_drive: str
    path: str
    local_download_folder: str
    redis_images_index: Optional[str] = f"images_index_{version}"
    redis_downloaded_images: Optional[str] = f"downloaded_images_{version}"
    redis_skipped_images: Optional[str] = f"skipped_images_{version}"
    max_image_size: Optional[tuple] = (1024, 1024)

    @validator('path')
    def no_leading_trailing_slash(cls, v):
        return v.strip('/')


@app.post('/download_training_images/')
async def download_training_files(drive_info: DownloadDriveInfo, background_tasks: BackgroundTasks):
    background_tasks.add_task(download_training_files_process, drive_info)
    return {'message': f"Downloading from path: {drive_info.rclone_drive}:{drive_info.path}..."}


def download_training_files_process(drive_info: DownloadDriveInfo):
    """
    Downloads images from our index, store them in training folder
    """

    try:
        os.mkdir(drive_info.local_download_folder)
    except FileExistsError:
        pass

    # Pull our whole image index
    images = r.hgetall(drive_info.redis_images_index)
    all_images = len(images)

    # Remove downloaded / skipped images
    [images.pop(downloaded_image, None) for downloaded_image in r.smembers(drive_info.redis_downloaded_images)]
    [images.pop(skipped_image, None) for skipped_image in r.hkeys(drive_info.redis_skipped_images)]

    # Decode our values
    images = {image_hash.decode('utf-8'): image_path.decode('utf-8') for image_hash, image_path in images.items()}

    new_images = len(images)

    logger.info(f"Already processed {all_images - new_images}...")

    for img_num, (image_hash, image_name) in enumerate(images.items(), start=1):
        logger.debug(f"downloading: {drive_info.rclone_drive}:/{drive_info.path}/{image_name}")
        download = subprocess.run(['rclone', 'copyto', fr'{drive_info.rclone_drive}:/{drive_info.path}/{image_name}', f"{drive_info.local_download_folder}/{image_hash}"]).returncode

        # Double check we downloaded correctly
        if download != 0:
            logger.error(f'Skipped image: {image_name}! Unable to download....')
            r.hset(drive_info.redis_skipped_images, image_hash, "unable to download")
            continue

        # Double check file type
        mime_type = mime.from_file(f'{drive_info.local_download_folder}/{image_hash}')
        if mime_type != "image/jpeg":
            os.remove(f'{drive_info.local_download_folder}/{image_hash}')
            logger.error(f'Skipped image: {image_hash} with MimeType: {mime_type}')
            r.hset(drive_info.redis_skipped_images, image_hash, mime_type)
            continue

        # Resize our image to smaller than 1024x1024
        try:
            # Load image
            img = Image.open(f'{drive_info.local_download_folder}/{image_hash}')
            # Delete the file
            os.remove(f'{drive_info.local_download_folder}/{image_hash}')
            # Resize it
            img.thumbnail(size=drive_info.max_image_size)
            # Save it
            img.save(f'{drive_info.local_download_folder}/{image_hash}.jpg', "JPEG")
        except OSError:
            logger.error(f"Unable to resize image: {image_hash}")
            r.hset(drive_info.redis_skipped_images, image_hash, 'OSError')
            continue

        # Update redis
        r.sadd(drive_info.redis_downloaded_images, image_hash)

        if img_num % 20 == 0:
            # Logging / stats
            logger.info(f"{img_num} images downloaded...")


#################################
#        Process Images         #
#################################


# class ProcessImagesInfo(BaseModel):
#     local_download_folder: str
#     redis_downloaded_images: Optional[str] = f"downloaded_images_{version}"
#     redis_processed_images: Optional[str] = f"processed_images_{version}"
#     redis_all_face_encodings: Optional[str] = f"all_face_encodings_{version}"
#
#
# @app.post('/find_faces/')
# async def find_face_encodings(process_images_info: ProcessImagesInfo, background_tasks: BackgroundTasks):
#     background_tasks.add_task(find_face_encodings_process, process_images_info)
#     return {'message': 'indexing faces...'}
#
#
# def find_face_encodings_process(process_images_info: ProcessImagesInfo):
#     """
#     Process downloaded photos and find faces / encodings
#     """
#     # Load all our images
#     images = r.smembers(process_images_info.redis_downloaded_images)
#     all_images = len(images)
#     logger.debug(f'{all_images} images sent for processing....')
#
#     # Remove processed images
#     [images.remove(processed_images) for processed_images in r.smembers(process_images_info.redis_processed_images)]
#     logger.debug(f'Skipping: {all_images - len(images)} (already processed)....')
#
#     # Decode images
#     images = [k.decode('utf-8') for k in images]
#
#     for img_num, image_hash in enumerate(images, start=1):
#
#         # Load up our image
#         image_path = f'{process_images_info.local_download_folder}/{image_hash}.jpg'
#
#         with open(image_path, 'rb') as img:
#             image = img.read()
#
#         payload = {"images": {"data": [b64encode(image).decode('utf-8')]}}
#
#         # Analyze our image / send it to insightface
#         try:
#             req = requests.post(url='http://10.0.42.70:31428/extract', data=json.dumps(payload))
#
#             faces = json.loads(req.text)[0]
#             logger.debug(f'Found {len(faces)} in {image_hash}')
#
#             # Loop through found faces
#             for face in faces:
#
#                 face_info = {
#                     'img_hash': image_hash,
#                     'encoding': face['vec'],
#                     'box': face['bbox']
#                 }
#
#                 r.sadd(process_images_info.redis_all_face_encodings, pickle.dumps(face_info))
#
#             r.sadd(process_images_info.redis_processed_images, image_hash)
#
#         except Exception as e:
#             logger.error(f"Unable to analyze image: {e}")
#
#         if img_num % 100 == 0:
#             # Logging / stats
#             logger.debug(f"{img_num} images processed...")


#################################
#       Gen Cluster Init        #
#################################


# class GenClusterInits(BaseModel):
#     filename_to_label_regex: str
#     rclone_drive: str
#     path: str
#     local_download_folder: str
#
#     max_image_size: Optional[tuple] = (1024, 1024)
#
#     redis_label_profile_map: Optional[str] = f"cluster_init_label_profile_map_{version}"
#     redis_images_index: Optional[str] = f"cluster_init_images_index_{version}"
#     redis_downloaded_images: Optional[str] = f"cluster_init_downloaded_images_{version}"
#     redis_skipped_images: Optional[str] = f"cluster_init_skipped_images_{version}"
#     redis_processed_images: Optional[str] = f"cluster_init_processed_images_{version}"
#     redis_all_face_encodings: Optional[str] = f"cluster_init_all_face_encodings_{version}"
#
#     @validator('path')
#     def no_leading_trailing_slash(cls, v):
#         return v.strip('/')
#
#
# @app.post('/gen_cluster_inits/')
# async def gen_cluster_inits(cluster_inits: GenClusterInits, background_tasks: BackgroundTasks):
#
#     index_drive_info = IndexDriveInfo(
#         rclone_drive=cluster_inits.rclone_drive,
#         path=cluster_inits.path,
#         redis_images_index=cluster_inits.redis_images_index
#     )
#
#     download_drive_info = DownloadDriveInfo(
#         rclone_drive=cluster_inits.rclone_drive,
#         path=cluster_inits.path,
#         local_download_folder=cluster_inits.local_download_folder,
#         redis_images_index=cluster_inits.redis_images_index,
#         redis_downloaded_images=cluster_inits.redis_downloaded_images,
#         redis_skipped_images=cluster_inits.redis_skipped_images,
#         max_image_size=cluster_inits.max_image_size
#     )
#
#     process_images_info = ProcessImagesInfo(
#         local_download_folder=cluster_inits.local_download_folder,
#         redis_downloaded_images=cluster_inits.redis_downloaded_images,
#         redis_processed_images=cluster_inits.redis_processed_images,
#         redis_all_face_encodings=cluster_inits.redis_all_face_encodings
#     )
#
#     background_tasks.add_task(gen_cluster_inits_process, cluster_inits, index_drive_info, download_drive_info, process_images_info)
#     return {'message': 'generating cluster init values...'}
#
#
# def gen_cluster_inits_process(
#         cluster_init_info: GenClusterInits,
#         index_drive_info: IndexDriveInfo,
#         download_drive_info: DownloadDriveInfo,
#         process_images_info: ProcessImagesInfo
# ):
#     """
#     Download cluster init files, find faces, map hashes to names
#     """
#     logger.debug(f"Using regex: {cluster_init_info.filename_to_label_regex}")
#     filename_to_label_regex = re.compile(cluster_init_info.filename_to_label_regex)
#
#     # Find and download our training images
#     logger.debug('Finding and downloading cluster inits....')
#     index_drive_process(index_drive_info)
#     download_training_files_process(download_drive_info)
#
#     # Grab image paths from redis
#     image_index = r.hgetall(index_drive_info.redis_images_index)
#     image_index = {img_hash.decode('utf-8'): img_path.decode('utf-8') for img_hash, img_path in image_index.items()}
#
#     # Grab label names from filenames, create cluster mapping
#     for img_hash, img_path in image_index.items():
#         label = img_path.rsplit('/', maxsplit=1)[1]
#         # TODO - This is staticly coded... needs to be fixed
#         lastname, firstname = filename_to_label_regex.findall(label)[-1].rsplit('_', maxsplit=1)
#         r.hset(cluster_init_info.redis_label_profile_map, key=img_hash, value=str(firstname.title() + lastname.title()))
#
#     logger.debug(f'Finding encodings....')
#     find_face_encodings_process(process_images_info)


#################################
#         Index Images          #
#################################


# class CreateImageMaps(BaseModel):
#     redis_all_face_encodings: Optional[str] = f"all_face_encodings_{version}"
#
#     redis_images_to_faces: Optional[str] = f"images_to_faces_{version}"
#     redis_faces_to_images: Optional[str] = f"faces_to_images_{version}"
#
#
# @app.post('/create_image_maps/')
# async def create_image_maps(background_tasks: BackgroundTasks, create_image_maps_info: CreateImageMaps = CreateImageMaps()):
#     background_tasks.add_task(create_image_maps_process, create_image_maps_info)
#     return {'message': 'creating image maps...'}
#
#
# def create_image_maps_process(create_image_maps_info: CreateImageMaps):
#     """
#     Create mappings from faces -> hashes and hashes -> faces
#     """
#
#     # Load our model
#     logger.debug(f"Loading model....")
#     cluster, profile_map = pickle.loads(r.get(create_image_maps_info.redis_trained_model))
#     profiles = list(profile_map.keys())
#
#     # Pull image hashes in the order they were trained w/
#     all_face_encodings_image_hashes = [pickle.loads(profile)['img_hash'] for profile in r.smembers(create_image_maps_info.redis_all_face_encodings)]
#
#     # Pull out corresponding labels
#     named_labels = [profiles[label] for label in cluster.labels_]
#
#     r.delete(create_image_maps_info.redis_images_to_faces)
#     r.delete(create_image_maps_info.redis_faces_to_images)
#     # Loop through labels and set corresponding values in redis
#     logger.debug(f"Mapping faces.....")
#     for name, img_hash in zip(named_labels, all_face_encodings_image_hashes):
#         # Grab current index, add this hash to list, reset the value
#         r.hset(create_image_maps_info.redis_images_to_faces, img_hash, json.dumps(json.loads(r.hget(create_image_maps_info.redis_images_to_faces, img_hash) or '[]') + [name]))
#         r.hset(create_image_maps_info.redis_faces_to_images, name, json.dumps(json.loads(r.hget(create_image_maps_info.redis_faces_to_images, name) or '[]') + [img_hash]))
#
#     logger.debug(f"Done!")


#################################
#         Label Images          #
#################################


class PredictImagesInfo(BaseModel):
    redis_known_encodings: Optional[str] = f"known_encodings_{version}"


@logger.catch
@app.post('/predict_label_image/')
async def predict_label_images(predict_images_info: PredictImagesInfo = PredictImagesInfo(), image: UploadFile = File(...)):

    # Create an image to draw on
    overlay_image = Image.open(image.file)

    draw = ImageDraw.Draw(overlay_image)

    payload = {"images": {"data": [b64encode(image.file.read()).decode('utf-8')]}}

    # try:
    req = requests.post(url='http://10.0.42.70:31428/extract', data=json.dumps(payload))

    faces = json.loads(req.text)[0]

    # Loop through faces
    for face in faces:
        top, right, bottom, left = faces['bbox']
        face_encoding = faces['vec']

        # See if the face is a match for the known face(s)
        profile_name = find_closest_match(profiles, face_encoding)

        # Draw a box around the face using the Pillow module
        draw.rectangle(((left, top), (right, bottom)), outline=(0, 0, 255))

        # Draw a label with a name below the face
        text_width, text_height = draw.textsize(profile_name)
        draw.rectangle(((left, bottom - text_height - 10), (right, bottom)), fill=(0, 0, 255), outline=(0, 0, 255))
        draw.text((left + 6, bottom - text_height - 5), profile_name, fill=(255, 255, 255, 255))

    del draw

    # Save it into a bytes stream
    output_image_stream = BytesIO()
    overlay_image.save(output_image_stream, format='JPEG')
    output_image_stream.seek(0)

    # return {'image': output_image_stream.getvalue(), 'accuracy_scores': accuracy_scores}
    return StreamingResponse(output_image_stream)

    # except Exception as e:
    #     logger.error(f"Unable to analyze image: {e}")


#################################
#         Find Person           #
#################################


class FindPerson(BaseModel):
    search_string: str
    rclone_drive: str
    path: str
    output_dir: str

    redis_images_index: Optional[str] = f"images_index_{version}"
    redis_faces_to_images: Optional[str] = f"faces_to_images_{version}"

    @validator('path')
    def no_leading_trailing_slash(cls, v):
        return v.strip('/')


@app.post('/find_person/')
async def find_person(find_person_info: FindPerson, background_tasks: BackgroundTasks):

    # Pull profiles
    all_profiles = {name.decode('utf-8'): images.decode('utf-8') for name, images in r.hgetall(find_person_info.redis_faces_to_images).items()}
    images_index = {img_hash.decode('utf-8'): path.decode('utf-8') for img_hash, path in r.hgetall(find_person_info.redis_images_index).items()}

    # Find closest match
    closest_match = fz_process.extractOne(find_person_info.search_string, all_profiles.keys())[0]

    # Start upload
    background_tasks.add_task(find_person_process, find_person_info, all_profiles, images_index, closest_match)

    # Return
    return {'message': f'uploading photos...', 'profile_name': closest_match}


async def find_person_process(find_person_info: FindPerson, all_profiles, images_index, closest_match):
    """
    Find all images of a specific person
    """

    # Asynchronously run rclone
    async def run(cmd):
        logger.debug(f'Running: {cmd}')
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        logger.debug(f'[{cmd!r} exited with {proc.returncode}]')
        if stdout:
            logger.debug(f'[stdout]\n{stdout.decode()}')
        if stderr:
            logger.debug(f'[stderr]\n{stderr.decode()}')

    subprocess.run(['rclone', 'mkdir', fr'{find_person_info.rclone_drive}:/{find_person_info.output_dir}/{closest_match}'])

    # Create a list of commands we need to run
    copy_commands = []
    for photo in json.loads(all_profiles[closest_match]):
        photo_path = images_index[photo]
        photo_name = photo_path.rsplit('/', maxsplit=1)[-1]
        logger.debug(f"Added {photo_name}")
        copy_commands.append(
            'rclone copyto '
            fr'"{find_person_info.rclone_drive}:/{find_person_info.path}/{photo_path}" '  # Source
            fr'"{find_person_info.rclone_drive}:/{find_person_info.output_dir}/{closest_match}/{photo_name}"'  # Destination
        )
            # ['rclone', 'copyto',
            #  fr'{find_person_info.rclone_drive}:/{find_person_info.path}/{photo_path}',  # Source
            #  fr'{find_person_info.rclone_drive}:/{find_person_info.output_dir}/{photo_name}']  # Destination
        # )

    await asyncio.gather(*[run(cmd) for cmd in copy_commands])

    logger.debug(f"Done finding {closest_match}!")

