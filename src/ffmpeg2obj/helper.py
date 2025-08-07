"""Module with helper classes for ffmpeg2obj"""

# pylint: disable=too-few-public-methods, too-many-instance-attributes, too-many-arguments

import argparse
import hashlib
import json
import os
import tempfile
import time
from datetime import timedelta
from typing import Any

import boto3
import botocore
import ffmpeg  # type: ignore[import-untyped]


class SplitArgs(argparse.Action):
    """Custom argparse action class borrowed from stackoverflow"""

    # https://stackoverflow.com/questions/52132076/argparse-action-or-type-for-comma-separated-list
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.split(","))


class ProcessingParams:
    """Class to describe processing parameres"""

    def __init__(
        self,
        resize: bool,
        target_width: int,
        target_height: int,
        video_codec: str,
        pix_fmt: str,
        langs: list[str],
        target_qp: int,
        target_crf: int,
    ) -> None:
        self.resize = resize
        self.video_codec = video_codec
        self.pix_fmt = pix_fmt
        self.langs = langs
        self.target_qp = target_qp
        self.target_crf = target_crf
        self.target_res: list[int] = [target_width, target_height]

    def to_json_str(self):
        """Returns JSON representation of ProcessingParams object"""
        return json.dumps(self, default=vars, sort_keys=True, indent=4)


class ProcessedFile:
    """Class to describe processed files"""

    def __init__(
        self,
        object_name: str,
        real_paths: list[str],
        file_extension: str,
        dst_dir: str,
        has_lockfile: bool,
        is_uploaded: bool,
        processing_params: ProcessingParams,
    ) -> None:
        self.object_name = object_name
        self.real_paths = real_paths
        self.file_extension = file_extension
        self.dst_dir = dst_dir if dst_dir.endswith("/") else dst_dir + "/"
        self.has_lockfile = has_lockfile
        self.is_uploaded = is_uploaded
        self.processing_params = processing_params
        self.hashed_name: str = hash_string(self.object_name)
        self.object_lock_file_name: str = self.object_name + ".lock"
        self.dst_path: str = self.dst_dir + self.object_name
        self.dst_hashed_path: str = (
            self.dst_dir + self.hashed_name + "." + self.file_extension
        )

    def __str__(self) -> str:
        out = []
        out += ["object_name: " + self.object_name]
        out += ["real_path: " + ",".join(self.real_paths)]
        out += ["has_lockfile: " + str(self.has_lockfile)]
        out += ["is_uploaded: " + str(self.is_uploaded)]
        out += ["hashed_name: " + self.hashed_name]
        return "\n".join(out)

    def update(self, obj_config: dict, bucket_name: str) -> None:
        """Updates ProcessedFile object instance attributes"""
        lock_file_exist = file_exists_in_bucket(
            self.object_lock_file_name, obj_config, bucket_name
        )
        uploaded_file_exist = file_exists_in_bucket(
            self.object_name, obj_config, bucket_name
        )
        if lock_file_exist is not None:
            self.has_lockfile = lock_file_exist
        if uploaded_file_exist is not None:
            self.is_uploaded = uploaded_file_exist

    def get_coded_res(self) -> list[int]:
        """Returns height and width for the file from real_path"""
        probe_result = ffmpeg.probe(self.real_paths[0])
        video_stream = list(
            filter(lambda x: x["codec_type"] == "video", probe_result["streams"])
        )[0]
        coded_res = [video_stream["coded_width"], video_stream["coded_height"]]
        return coded_res

    def convert(self, verbose: bool = False) -> tuple[str, str, bool, timedelta]:
        """Runs ffmpeg against the file from real_path and stores it in /tmp"""
        convert_succeded = False
        concat_enabled = len(self.real_paths) > 1
        # core opts
        opts_dict: dict[str, Any] = {
            "c:v": self.processing_params.video_codec,
            "c:a": "copy",
            "c:s": "copy",
            "v": "error",
        }
        # conditional opts
        if (
            self.processing_params.pix_fmt is not None
            and self.processing_params.video_codec != "copy"
        ):
            opts_dict.update({"pix_fmt": self.processing_params.pix_fmt})
        if self.processing_params.target_crf is not None:
            opts_dict.update({"crf": str(self.processing_params.target_crf)})
        elif self.processing_params.target_qp is not None:
            opts_dict.update({"qp": str(self.processing_params.target_qp)})
        lang_map = []
        for lang in self.processing_params.langs:
            lang_map.append("0:m:language:" + lang)
        lang_dict = {"map": tuple(lang_map)}
        opts_dict.update(lang_dict)
        if (
            self.processing_params.resize and
            self.processing_params.target_res != self.get_coded_res()
        ):
            scale_dict = {
                "vf": "scale="
                + ":".join(str(x) for x in self.processing_params.target_res)
            }
            opts_dict.update(scale_dict)
        if concat_enabled:
            temp_file_byte_contents = (
                "\n".join(f"file '{path}'" for path in self.real_paths) + "\n"
            ).encode()
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(temp_file_byte_contents)
            input_file = temp_file.name
            stream = ffmpeg.input(input_file, f="concat", safe="0")
        else:
            input_file = self.real_paths[0]
            stream = ffmpeg.input(input_file)
        stream = ffmpeg.output(stream, self.dst_hashed_path, **opts_dict)
        start_time = time.monotonic()
        if verbose:
            print(" ".join(ffmpeg.compile(stream)))
        try:
            std_out, std_err = ffmpeg.run(
                stream, capture_stdout=True, capture_stderr=True
            )
        except ffmpeg.Error as e:
            print(f"Error occured: {e}")
            end_time = time.monotonic()
            duration = timedelta(seconds=end_time - start_time)
            return e.stdout.decode(), e.stderr.decode(), convert_succeded, duration
        convert_succeded = True
        if concat_enabled:
            os.remove(input_file)
        end_time = time.monotonic()
        duration = timedelta(seconds=end_time - start_time)
        return std_out.decode(), std_err.decode(), convert_succeded, duration

    def create_lock_file(self, obj_config: dict, bucket_name: str) -> bool:
        """Creates empty lock file on object storage bucket"""
        obj_client = boto3.client("s3", **obj_config)
        try:
            obj_client.put_object(
                Bucket=bucket_name,
                Key=self.object_lock_file_name,
                Body=self.processing_params.to_json_str().encode("UTF-8"),
            )
        except botocore.exceptions.ClientError as e:
            print(e)
            return False
        self.has_lockfile = True
        return True

    def upload(self, obj_config: dict, bucket_name: str) -> tuple[bool, timedelta]:
        """Uploads converted file from /tmp to object storage bucket"""
        obj_client = boto3.client("s3", **obj_config)
        start_time = time.monotonic()
        try:
            obj_client.upload_file(self.dst_hashed_path, bucket_name, self.object_name)
        except botocore.exceptions.ClientError as e:
            print(e)
        else:
            self.is_uploaded = True
        finally:
            end_time = time.monotonic()
            duration = timedelta(seconds=end_time - start_time)
        return self.is_uploaded, duration


def file_exists_in_bucket(file: str, obj_config: dict, bucket_name: str) -> bool | None:
    """Checks if given file exists in requested bucket"""
    obj_client = boto3.client("s3", **obj_config)
    try:
        obj_client.head_object(Bucket=bucket_name, Key=file)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        return None


def hash_string(string: str) -> str:
    """Hashes input string and returns hexdigest for it"""
    hasher = hashlib.sha256()
    hasher.update(string.encode("utf8"))
    return hasher.hexdigest()
