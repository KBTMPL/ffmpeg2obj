"""Module with helper classes for ffmpeg2obj"""

# pylint: disable=too-few-public-methods, too-many-instance-attributes, too-many-arguments

import hashlib
from typing import Any
import boto3
import botocore
import ffmpeg  # type: ignore[import-untyped]


class ProcessedFile:
    """Class to describe processed files"""

    def __init__(
        self,
        object_name: str,
        real_path: str,
        has_lockfile: bool,
        is_uploaded: bool,
        file_extension: str,
        tmp_dir: str,
        target_width: int,
        target_height: int,
        video_codec: str,
        pix_fmt: str,
        langs: list[str],
        target_qp: int,
        target_crf: int,
    ) -> None:
        self.object_name = object_name
        self.real_path = real_path
        self.has_lockfile = has_lockfile
        self.is_uploaded = is_uploaded
        self.file_extension = file_extension
        self.tmp_dir = tmp_dir if tmp_dir.endswith("/") else tmp_dir + "/"
        self.video_codec = video_codec
        self.pix_fmt = pix_fmt
        self.langs = langs
        self.target_qp = target_qp
        self.target_crf = target_crf
        self.target_res: list[int] = [target_width, target_height]
        self.hashed_name: str = hash_string(self.object_name)
        self.object_lock_file_name: str = self.object_name + ".lock"
        self.tmp_path: str = self.tmp_dir + self.hashed_name + "." + self.file_extension

    def __str__(self) -> str:
        out = []
        out += ["object_name: " + self.object_name]
        out += ["real_path: " + self.real_path]
        out += ["has_lockfile: " + str(self.has_lockfile)]
        out += ["is_uploaded: " + str(self.is_uploaded)]
        out += ["hashed_name: " + self.hashed_name]
        return "\n".join(out)

    def update(self, obj_config: dict, bucket_name: str) -> None:
        """Updates ProcessedFile object instance attributes"""
        lock_file_exist = file_exists(
            self.object_lock_file_name, obj_config, bucket_name
        )
        uploaded_file_exist = file_exists(self.object_name, obj_config, bucket_name)
        if lock_file_exist is not None:
            self.has_lockfile = lock_file_exist
        if uploaded_file_exist is not None:
            self.is_uploaded = uploaded_file_exist

    def get_coded_res(self) -> list[int]:
        """Returns height and width for the file from real_path"""
        probe_result = ffmpeg.probe(self.real_path)
        video_stream = list(
            filter(lambda x: x["codec_type"] == "video", probe_result["streams"])
        )[0]
        coded_res = [video_stream["coded_width"], video_stream["coded_height"]]
        return coded_res

    def convert(self) -> tuple[Any, Any]:
        """Runs ffmpeg against the file from real_path and stores it in /tmp"""
        # core opts
        opts_dict: dict[str, Any] = {
            "c:v": self.video_codec,
            "pix_fmt": self.pix_fmt,
            "c:a": "copy",
            "c:s": "copy",
            "v": "quiet",
        }
        # conditional opts
        if self.target_crf is not None:
            opts_dict.update({"crf": str(self.target_crf)})
        elif self.target_qp is not None:
            opts_dict.update({"qp": str(self.target_qp)})
        lang_map = []
        for lang in self.langs:
            lang_map.append("0:m:language:" + lang)
        lang_dict = {"map": tuple(lang_map)}
        opts_dict.update(lang_dict)
        if self.target_res != self.get_coded_res():
            scale_dict = {"vf": "scale=" + ":".join(str(x) for x in self.target_res)}
            opts_dict.update(scale_dict)
        stream = ffmpeg.input(self.real_path)
        stream = ffmpeg.output(stream, self.tmp_path, **opts_dict)
        out, err = ffmpeg.run(stream)
        return out, err

    def create_lock_file(self, obj_config: dict, bucket_name: str) -> bool:
        """Creates empty lock file on object storage bucket"""
        obj_client = boto3.client("s3", **obj_config)
        try:
            obj_client.put_object(Bucket=bucket_name, Key=self.object_lock_file_name)
        except botocore.exceptions.ClientError as e:
            print(e)
            return False
        self.has_lockfile = True
        return self.has_lockfile

    def upload(self, obj_config: dict, bucket_name: str) -> bool:
        """Uploads converted file from /tmp to object storage bucket"""
        obj_client = boto3.client("s3", **obj_config)
        try:
            obj_client.upload_file(self.hashed_name, bucket_name, self.object_name)
        except botocore.exceptions.ClientError as e:
            print(e)
            return False
        self.is_uploaded = True
        return self.is_uploaded


def file_exists(file: str, obj_config: dict, bucket_name: str) -> bool | None:
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
