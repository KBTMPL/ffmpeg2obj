"""
Main executable for simple project that compresses blu ray movie library and stores it in obj
"""

# pylint: disable=too-many-arguments,too-many-locals

import argparse
import os
import unicodedata
from queue import Queue
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, wait
import boto3
import ffmpeg  # type: ignore[import-untyped]

from ffmpeg2obj.helper import ProcessedFile, ProcessingParams


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
        "--noop",
        dest="noop",
        action="store_true",
        default=False,
        help="script executes but takes no action",
    )

    parser.add_argument(
        "--force-cleanup",
        dest="force_cleanup",
        action="store_true",
        default=False,
        help="cleans up even on upload failure",
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
        "--resize",
        dest="resize",
        action="store_true",
        default=False,
        help="scale input files to height x width",
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
        "-qp",
        dest="target_qp",
        type=int,
        help="Quantization Parameter for the media files to be transcoded",
    )

    qf_group.add_argument(
        "-crf",
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
    processing_params: ProcessingParams,
) -> list[ProcessedFile]:
    """Returns list of processed files based on collected data"""
    processed_files = []
    for object_name, real_path in source_files.items():
        is_uploaded = object_name in bucket_objects
        has_lockfile = object_name + ".lock" in bucket_objects
        processed_files.append(
            ProcessedFile(
                object_name,
                real_path,
                file_extension,
                tmp_dir,
                has_lockfile,
                is_uploaded,
                processing_params,
            )
        )
    return processed_files


def convert_and_upload(
    queue: Queue,
    lock: Lock,
    obj_config: dict,
    bucket_name: str,
    force_cleanup: bool,
    noop: bool,
) -> bool:
    """Converts and uploads media taken from queue"""
    processed_file: ProcessedFile = queue.get()
    conversion_failed = False
    upload_failed = False
    if not processed_file.has_lockfile:
        with lock:
            if not noop:
                # TODO: improve overall ffmpeg-python error handling and maybe show status
                try:
                    print("Starting conversion for " + processed_file.object_name)
                    processed_file.convert()
                except ffmpeg.Error:
                    conversion_failed = True
                else:
                    processed_file.create_lock_file(obj_config, bucket_name)
            else:
                print("Would have start conversion for " + processed_file.object_name)
    if not processed_file.is_uploaded and os.path.isfile(processed_file.tmp_path):
        if not noop:
            print("Starting upload for " + processed_file.object_name)
            upload_failed = not processed_file.upload(obj_config, bucket_name)
            if not upload_failed or force_cleanup:
                os.remove(processed_file.tmp_path)
        else:
            print("Would have start upload for " + processed_file.object_name)
    return not (conversion_failed or upload_failed)


def main():
    """Gets the job done"""
    args = parse_args()

    source_files = get_source_files(
        args.source_dir, args.ignored_subdir, args.obj_prefix, args.file_extension
    )

    obj_resource = get_obj_resource(OBJ_CONFIG)

    if selected_bucket_exist(obj_resource, args.bucket_name):
        if args.noop:
            print("noop enabled, will not take any actions")
        bucket_files = get_bucket_files(obj_resource, args.bucket_name)
        processing_params = ProcessingParams(
            args.resize,
            args.target_width,
            args.target_width,
            args.video_codec,
            args.pix_fmt,
            args.langs,
            args.target_qp,
            args.target_crf,
        )
        processed_files = get_processed_files(
            source_files,
            bucket_files,
            args.file_extension,
            args.tmp_dir,
            processing_params,
        )
        jobs = Queue()
        for file in processed_files:
            jobs.put(file)
        lock = Lock()
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(
                    convert_and_upload,
                    jobs,
                    lock,
                    OBJ_CONFIG,
                    args.bucket_name,
                    args.force_cleanup,
                    args.noop,
                )
                for _ in range(len(processed_files))
            ]
        wait(futures)


if __name__ == "__main__":
    main()
