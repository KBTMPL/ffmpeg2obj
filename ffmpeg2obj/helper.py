"""Module with helper classes for ffmpeg2obj"""


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

    def __str__(self) -> str:
        out = []
        out += ["object_name: " + self.object_name]
        out += ["real_path: " + self.real_path]
        out += ["is_locked: " + str(self.is_locked)]
        out += ["is_uploaded: " + str(self.is_uploaded)]
        out += ["hashed_name: " + str(self.hashed_name)]
        return "\n".join(out)
