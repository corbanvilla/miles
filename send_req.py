import requests
import json

cluster_inits = {
  "filename_to_label_regex": "_(.*?)_01\\.",
  "rclone_drive": "2021_gdrive",
  "path": "01- Photos/01- Academics/Lifetouch",
  "local_download_folder": "/training/cluster_init",
  "redis_images_index": "images_index_cluster_init",
  "redis_downloaded_images": "downloaded_images_cluster_init",
  "redis_skipped_images": "skipped_images_cluster_init",
  "redis_processed_images": "processed_images_cluster_init",
  "redis_all_face_encodings": "face_encodings_cluster_init"
}


def call_gen_cluster_images():
    url = 'http://10.0.42.70:31427/gen_cluster_inits/'

    x = requests.post(url, data=json.dumps(cluster_inits))

    print(x.text)


# call_gen_cluster_images()


index_files = {
    "rclone_drive": "2021_gdrive",
    "path": "01- Photos",
}


def call_index_images():
    url = 'http://10.0.42.70:31427/update_image_index/'

    x = requests.post(url, data=json.dumps(index_files))

    print(x.text)


# call_index_images()


download_files = {
    "rclone_drive": "2021_gdrive",
    "path": "01- Photos",
    "local_download_folder": "/training/2048",
    "max_image_size": (2048, 2048)
}


def download_images():

    url = 'http://10.0.42.70:31427/download_training_images/'

    x = requests.post(url, data=json.dumps(download_files))

    print(x.text)


# download_images()


process_images = {
    "local_download_folder": "/training/2048",
    "face_model": "cnn"
}


# def call_process_images():
#     url = 'http://10.0.42.70:31427/find_faces/'
#
#     x = requests.post(url, data=json.dumps(process_images))
#
#     print(x.text)


# call_process_images()


train_model = {
  "redis_cluster_init_face_encodings": "face_encodings_cluster_init",
  # "redis_all_face_encodings": "all_face_encodings_v2"
}


# def call_train_model():
#     url = 'http://10.0.42.70:31427/train_model/'
#
#     x = requests.post(url, data=json.dumps(train_model))
#
#     print(x.text)
#
#
# call_train_model()


find_person = {
    "search_string": "CorbinVia",
    "rclone_drive": "2021_gdrive",
    "path": "01- Photos",
    "output_dir": "Face Recognition",
}


def call_find_person():
    url = 'http://10.0.42.70:31427/find_person/'

    x = requests.post(url, data=json.dumps(find_person))

    print(x.text)


call_find_person()


def upload_images():
    url = 'http://10.0.42.70:31427/predict_label_image/'

    # image =
    # img_data = image.read()
    # image.close()

    # print(len(img_data))

    # x = requests.post(url, files={'image': open('/Users/animcogn/Desktop/bests@mosts raycello&corban.jpg', 'rb')})
    x = requests.post(url, files={'image': open('/Users/animcogn/Downloads/007_LAMBERT_MILES.JPG', 'rb')})

    print(x.headers)

    temp = open('temp.jpg', 'wb')
    temp.write(x.content)
    temp.close()


# upload_images()
