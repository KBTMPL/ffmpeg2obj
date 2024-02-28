"""Module with helper classes for ffmpeg2obj"""

import boto3
import botocore


class ProcessedFile:
    """Class to describe processed files"""

    def __init__(
        self, object_name: str, real_path: str, is_locked: bool, is_uploaded: bool
    ) -> None:
        self.object_name = object_name
        self.real_path = real_path
        self.is_locked = is_locked
        self.is_uploaded = is_uploaded
        self.hashed_name: int = hash(object_name)
        self.object_lock_file_name = self.object_name + ".lock"

    def __str__(self) -> str:
        out = []
        out += ["object_name: " + self.object_name]
        out += ["real_path: " + self.real_path]
        out += ["is_locked: " + str(self.is_locked)]
        out += ["is_uploaded: " + str(self.is_uploaded)]
        out += ["hashed_name: " + str(self.hashed_name)]
        return "\n".join(out)

    def update(self, obj_config: dict, bucket_name: str) -> None:
        """Updates ProcessedFile object instance attributes"""
        self.is_locked = file_exists(
            self.object_lock_file_name, obj_config, bucket_name
        )
        self.is_uploaded = file_exists(self.object_name, obj_config, bucket_name)


def file_exists(file: str, obj_config: dict, bucket_name: str) -> bool:
    """Checks if given file exists in requested bucket"""
    obj_client = boto3.client("s3", **obj_config)
    try:
        obj_client.head_object(Bucket=bucket_name, Key=file)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        return False
