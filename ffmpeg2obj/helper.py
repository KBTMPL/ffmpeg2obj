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
        hasher = hashlib.sha256()
        hasher.update(self.object_name.encode("utf8"))
        self.hashed_name: str = hasher.hexdigest()
        self.object_lock_file_name = self.object_name + ".lock"

    def __str__(self) -> str:
        out = []
        out += ["object_name: " + self.object_name]
        out += ["real_path: " + self.real_path]
        out += ["is_locked: " + str(self.is_locked)]
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
            self.is_locked = lock_file_exist
        if uploaded_file_exist is not None:
            self.is_uploaded = uploaded_file_exist

    def upload(self, obj_config: dict, bucket_name: str) -> bool:
        """Uploads converted file from /tmp to object storage bucket"""
        obj_client = boto3.client("s3", **obj_config)
        try:
            obj_client.upload_file(self.hashed_name, bucket_name, self.object_name)
        except botocore.exceptions.ClientError as e:
            print(e)
            return False
        return True


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
