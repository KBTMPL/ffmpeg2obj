"""
Main executable for simple project that compresses blu ray movie library and stores it in obj
"""

# pylint: disable=too-many-arguments,too-many-locals

import argparse
import os
import unicodedata

import boto3

from ffmpeg2obj.helper import ProcessedFile

# from threading import Thread
# from queue import Queue


OBJ_ACCESS_KEY_ID = os.environ.get("aws_access_key_id", None)
OBJ_SECRET_ACCESS_KEY = os.environ.get("aws_secret_access_key", None)
OBJ_ENDPOINT_URL = os.environ.get("endpoint_url", None)

OBJ_CONFIG = {
    "aws_access_key_id": OBJ_ACCESS_KEY_ID,
    "aws_secret_access_key": OBJ_SECRET_ACCESS_KEY,
    "endpoint_url": OBJ_ENDPOINT_URL,
}


class SplitArgs(argparse.Action):
    """Custom argparse action class borrowed from stackoverflow"""

    # https://stackoverflow.com/questions/52132076/argparse-action-or-type-for-comma-separated-list
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.split(","))


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
        "-t",
        "--tmp-dir",
        dest="tmp_dir",
        type=str,
        default="/tmp/",
        help="temporary directory for media to be transcoded",
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
        required=True,
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

    parser.add_argument(
        "-vc",
        "--video-codec",
        dest="video_codec",
        type=str,
        default="libx265",
        help="video codec for transcoding of the media files",
    )

    parser.add_argument(
        "--pix-fmt",
        dest="pix_fmt",
        type=str,
        default="yuv420p10le",
        help="pix fmt for transcoding of the media files",
    )

    parser.add_argument(
        "-l",
        "--languages",
        dest="langs",
        action=SplitArgs,
        default=["pol", "eng"],
        help="selected languages transcoding of the media files",
    )

    parser.add_argument(
        "--width",
        dest="target_width",
        type=int,
        default=1920,
        help="target width for the media files to be transcoded",
    )

    parser.add_argument(
        "--height",
        dest="target_height",
        type=int,
        default=1080,
        help="target height for the media files to be transcoded",
    )

    qf_group = parser.add_mutually_exclusive_group(required=True)

    qf_group.add_argument(
        "--qp",
        dest="target_qp",
        type=int,
        help="Quantization Parameter for the media files to be transcoded",
    )

    qf_group.add_argument(
        "--crf",
        dest="target_crf",
        type=int,
        help="Constant Rate Factor for the media files to be transcoded",
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
                real_path = unicodedata.normalize("NFC", os.path.join(root, name))
                object_name = unicodedata.normalize(
                    "NFC", real_path.replace(source_dir, obj_prefix)
                )
                source_file_dict = {object_name: real_path}
                source_files.update(source_file_dict)
    return source_files


def get_obj_resource(obj_config: dict) -> boto3.resource.__class__:
    """Returns object storage client"""
    obj_resource = boto3.resource("s3", **obj_config)
    return obj_resource


def selected_bucket_exist(
    obj_resource: boto3.resource.__class__, bucket_name: str
) -> bool:
    """Checks whether selected bucket exists"""
    buckets = obj_resource.buckets.all()
    return bucket_name in list(bucket.name for bucket in buckets)


def get_bucket_files(obj_resource: boto3.resource.__class__, bucket_name: str):
    """Returns objects from given object storage bucket"""
    bucket_files = list(
        unicodedata.normalize("NFC", file.key)
        for file in obj_resource.Bucket(bucket_name).objects.all()
    )
    return bucket_files


def get_processed_files(
    source_files: dict,
    bucket_objects: list,
    file_extension: str,
    tmp_dir: str,
    target_width: int,
    target_height: int,
    video_codec: str,
    pix_fmt: str,
    langs: list[str],
    target_qp: int,
    target_crf: int,
) -> list[ProcessedFile]:
    """Returns list of processed files based on collected data"""
    processed_files = []
    for object_name, real_path in source_files.items():
        is_uploaded = object_name in bucket_objects
        is_locked = object_name + ".lock" in bucket_objects
        processed_files.append(
            ProcessedFile(
                object_name,
                real_path,
                is_locked,
                is_uploaded,
                file_extension,
                tmp_dir,
                target_width,
                target_height,
                video_codec,
                pix_fmt,
                langs,
                target_qp,
                target_crf,
            )
        )
    return processed_files


def filter_locked_processed_files(
    processed_files: list[ProcessedFile],
) -> list[ProcessedFile]:
    """Returns processed files that are not locked"""
    unlocked_processed_files = list(filter(lambda x: not x.is_locked, processed_files))
    return unlocked_processed_files


def filter_uploaded_processed_files(
    processed_files: list[ProcessedFile],
) -> list[ProcessedFile]:
    """Returns processed files that are not uploaded"""
    # TODO: consider adding and x.is_locked
    not_uploaded_processed_files = list(
        filter(lambda x: not x.is_uploaded, processed_files)
    )
    return not_uploaded_processed_files


def main():
    """Gets the job done"""
    args = parse_args()

    source_files = get_source_files(
        args.source_dir, args.ignored_subdir, args.obj_prefix, args.file_extension
    )

    obj_resource = get_obj_resource(OBJ_CONFIG)

    if selected_bucket_exist(obj_resource, args.bucket_name):
        bucket_files = get_bucket_files(obj_resource, args.bucket_name)
        processed_files = get_processed_files(
            source_files,
            bucket_files,
            args.file_extension,
            args.tmp_dir,
            args.target_width,
            args.target_height,
            args.video_codec,
            args.pix_fmt,
            args.langs,
            args.target_qp,
            args.target_crf,
        )
        unlocked_processed_files = filter_locked_processed_files(processed_files)
        not_uploaded_processed_files = filter_uploaded_processed_files(processed_files)

        print("Processed files count: " + str(len(processed_files)))
        print("Unlocked processed files count: " + str(len(unlocked_processed_files)))
        print(
            "Not uploaded processed files count: "
            + str(len(not_uploaded_processed_files))
        )
        print()

        result = unlocked_processed_files[0].convert()
        print(result)


if __name__ == "__main__":
    main()
