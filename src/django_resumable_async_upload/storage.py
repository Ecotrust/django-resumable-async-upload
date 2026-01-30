import datetime

import posixpath

try:
    from django.core.files.storage import storages, InvalidStorageError
except ImportError:
    # Fallback for older Django versions
    storages = None
    InvalidStorageError = None

from django.conf import settings
from django.utils.encoding import force_str


class ResumableStorage(object):
    def __init__(self):
        # For backward compatibility, still check old settings
        self.persistent_storage_name = getattr(
            settings, "ADMIN_RESUMABLE_STORAGE", None
        )
        self.chunk_storage_name = getattr(
            settings, "ADMIN_RESUMABLE_CHUNK_STORAGE", None
        )

    def get_chunk_storage(self, *args, **kwargs):
        """
        Returns storage class specified in settings as ADMIN_RESUMABLE_CHUNK_STORAGE.
        Defaults to django.core.files.storage.FileSystemStorage.
        Chunk storage should be highly available for the server as saved chunks must be copied by the server
        for saving merged version in persistent storage.
        """
        if self.chunk_storage_name:
            # If a specific storage backend is configured, use it
            if storages:
                # Django 4.2+ - check if it's a STORAGES key or class path
                try:
                    return storages[self.chunk_storage_name]
                except (KeyError, InvalidStorageError):
                    # Not a STORAGES key, treat as class path
                    from django.core.files.storage import get_storage_class

                    storage_class = get_storage_class(self.chunk_storage_name)
                    return storage_class(*args, **kwargs)
            else:
                # Older Django - use get_storage_class
                from django.core.files.storage import get_storage_class

                storage_class = get_storage_class(self.chunk_storage_name)
                return storage_class(*args, **kwargs)
        else:
            # Default to local FileSystemStorage for performance
            # (chunks should not be written to remote storage like S3)
            if storages:
                from django.core.files.storage import FileSystemStorage

                return FileSystemStorage(*args, **kwargs)
            else:
                from django.core.files.storage import get_storage_class

                storage_class = get_storage_class(
                    "django.core.files.storage.FileSystemStorage"
                )
                return storage_class(*args, **kwargs)

    def get_persistent_storage(self, *args, **kwargs):
        """
        Returns storage class specified in settings as ADMIN_RESUMABLE_STORAGE
        or DEFAULT_FILE_STORAGE if the former is not found.

        Defaults to django.core.files.storage.FileSystemStorage.
        """
        if storages:
            # Django 4.2+ with STORAGES setting
            if self.persistent_storage_name:
                # If a specific storage backend is configured, use it
                from django.core.files.storage import get_storage_class

                storage_class = get_storage_class(self.persistent_storage_name)
                return storage_class(*args, **kwargs)
            else:
                # Use default storage from STORAGES setting
                return storages["default"]
        else:
            # Fallback for older Django versions
            from django.core.files.storage import get_storage_class

            persistent_storage_class_name = self.persistent_storage_name or getattr(
                settings,
                "DEFAULT_FILE_STORAGE",
                "django.core.files.storage.FileSystemStorage",
            )
            storage_class = get_storage_class(persistent_storage_class_name)

            return storage_class(*args, **kwargs)

    def full_filename(self, filename, upload_to, instance=None):
        if callable(upload_to):
            filename = upload_to(instance, filename)
        else:
            dirname = force_str(datetime.datetime.now().strftime(force_str(upload_to)))
            filename = posixpath.join(dirname, filename)
        return self.get_persistent_storage().generate_filename(filename)
