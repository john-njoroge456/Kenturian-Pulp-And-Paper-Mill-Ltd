from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateFileStorage(FileSystemStorage):
    """Files saved here are never given a public web address."""

    def __init__(self):
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT)

    def url(self, name):
        return ""   # no public link; staff use the protected admin download


def private_storage():
    return PrivateFileStorage()
