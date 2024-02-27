"""
Main executable for simple project that compresses blu ray movie library and stores it in obj
"""

import argparse
import os

import boto3

from ffmpeg2obj.helper import ProcessedFile

# from threading import Thread
# from queue import Queue
# import ffmpeg


OBJ_ACCESS_KEY_ID = os.environ.get("aws_access_key_id", None)
OBJ_SECRET_ACCESS_KEY = os.environ.get("aws_secret_access_key", None)
OBJ_ENDPOINT_URL = os.environ.get("endpoint_url", None)

OBJ_CONFIG = {
    "aws_access_key_id": OBJ_ACCESS_KEY_ID,
    "aws_secret_access_key": OBJ_SECRET_ACCESS_KEY,
    "endpoint_url": OBJ_ENDPOINT_URL,
}


def parse_args() -> argparse.Namespace:
    """Defines options for the tool"""
    parser = argparse.ArgumentParser(
        description="Simple tool to compress blu ray movie library and store it in obj"
    )

    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="show additional information",
    )

    parser.add_argument(
        "-s",
        "--source-dir",
        dest="source_dir",
        type=str,
        default=".",
        help="source directory for media to be transcoded",
    )

    parser.add_argument(
        "-i",
        "--ignored-subdir",
        dest="ignored_subdir",
        type=str,
        default="extras",
        help="ignored subdirectories",
    )

    parser.add_argument(
        "-o",
        "--obj-prefix",
        dest="obj_prefix",
        type=str,
        default="",
        help="source directory for media to be transcoded",
    )

    parser.add_argument(
        "-b",
        "--bucket-name",
        dest="bucket_name",
        type=str,
        default="",
        help="source directory for media to be transcoded",
    )

    parser.add_argument(
        "-e",
        "--file-extension",
        dest="file_extension",
        type=str,
        default="mkv",
        help="extension for the media files to be transcoded",
    )

    return parser.parse_args()


def get_source_files(
    source_dir: str, ignored_subdir: str, obj_prefix: str, file_extension: str
) -> dict[str, str]:
    """Looks for source files"""
    source_files = {}
    for root, _, files in os.walk(source_dir):
        for name in files:
            if ignored_subdir not in root and file_extension in name:
                real_path = os.path.join(root, name)
                object_name = obj_prefix + real_path.lstrip(source_dir)
                source_files.update({object_name: real_path})
    return source_files


def get_obj_client(obj_config: dict) -> boto3.client.__class__:
    """Returns object storage client"""
    obj_client = boto3.client("s3", **obj_config)
    return obj_client


def selected_bucket_exist(obj_client: boto3.client.__class__, bucket_name: str) -> bool:
    """Checks whether selected bucket exists"""
    buckets = obj_client.list_buckets()["Buckets"]
    return bucket_name in list(bucket["Name"] for bucket in buckets)


def get_bucket_objects(obj_client: boto3.client.__class__, bucket_name: str):
    """Returns objects from given object storage bucket"""
    return list(
        obj["Key"] for obj in obj_client.list_objects(Bucket=bucket_name)["Contents"]
    )


def get_processed_files(
    source_files: dict, bucket_objects: list
) -> list[ProcessedFile]:
    """Returns list of processed files based on collected data"""
    processed_files = []
    for object_name, real_path in source_files.items():
        is_uploaded = object_name in bucket_objects
        is_locked = object_name + ".lock" in bucket_objects
        processed_files.append(
            ProcessedFile(object_name, real_path, is_locked, is_uploaded)
        )
    return processed_files


def get_locked_processed_files(
    processed_files: list[ProcessedFile],
) -> list[ProcessedFile]:
    """Returns processed files that are locked"""
    return list(filter(lambda x: not x.is_locked, processed_files))


def get_uploaded_processed_files(
    processed_files: list[ProcessedFile],
) -> list[ProcessedFile]:
    """Returns processed files that are uploaded"""
    return list(filter(lambda x: not x.is_uploaded, processed_files))


def main():
    """Gets the job done"""
    args = parse_args()

    source_files = get_source_files(
        args.source_dir, args.ignored_subdir, args.obj_prefix, args.file_extension
    )

    obj_client = get_obj_client(OBJ_CONFIG)

    if selected_bucket_exist(obj_client, args.bucket_name):
        bucket_objects = get_bucket_objects(obj_client, args.bucket_name)
        processed_files = get_processed_files(source_files, bucket_objects)
        locked_processed_files = get_locked_processed_files(processed_files)
        uploaded_processed_files = get_uploaded_processed_files(processed_files)
        print(f"Locked files count: {len(locked_processed_files)}")
        print(f"Uploaded files count: {len(uploaded_processed_files)}")


if __name__ == "__main__":
    main()
