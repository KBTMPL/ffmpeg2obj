"""Module with helper classes for ffmpeg2obj"""


class ProcessedFile:
    """Class to describe processed files"""
    def __init__(
        self,
        object_name: str,
        real_path: str,
        is_locked: bool,
        is_uploaded: bool
    ) -> None:
        self.object_name = object_name
        self.real_path = real_path
        self.is_locked = is_locked
        self.is_uploaded = is_uploaded
        self.hashed_name: int = hash(object_name)
