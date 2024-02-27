"""Module with helper classes for ffmpeg2obj"""


class ProcessedFile:
    """Class to describe processed files"""
    def __init__(
        self,
        object_name,
        real_path,
        is_locked,
        is_uploaded
        
    ) -> None:
        self.object_name = object_name
        self.real_path = real_path
        self.is_locked = is_locked
        self.is_uploaded = is_uploaded
