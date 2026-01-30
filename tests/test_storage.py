from unittest.mock import Mock, patch
from django.test import override_settings
from django.core.files.storage import FileSystemStorage

from django_resumable_async_upload.storage import ResumableStorage


class TestResumableStorage:
    """Tests for ResumableStorage class."""

    def test_init_without_custom_settings(self):
        """Test initialization with no custom storage settings."""
        storage = ResumableStorage()
        assert storage.persistent_storage_name is None
        assert storage.chunk_storage_name is None

    @override_settings(ADMIN_RESUMABLE_STORAGE="custom.storage.Backend")
    def test_init_with_custom_persistent_storage(self):
        """Test initialization with custom persistent storage setting."""
        storage = ResumableStorage()
        assert storage.persistent_storage_name == "custom.storage.Backend"
        assert storage.chunk_storage_name is None

    @override_settings(ADMIN_RESUMABLE_CHUNK_STORAGE="custom.chunk.Storage")
    def test_init_with_custom_chunk_storage(self):
        """Test initialization with custom chunk storage setting."""
        storage = ResumableStorage()
        assert storage.persistent_storage_name is None
        assert storage.chunk_storage_name == "custom.chunk.Storage"

    def test_get_chunk_storage_default(self):
        """Test that chunk storage defaults to FileSystemStorage."""
        storage = ResumableStorage()
        chunk_storage = storage.get_chunk_storage()
        assert isinstance(chunk_storage, FileSystemStorage)

    @override_settings(
        ADMIN_RESUMABLE_CHUNK_STORAGE="django.core.files.storage.FileSystemStorage"
    )
    def test_get_chunk_storage_custom_class_path(self):
        """Test chunk storage with custom class path."""
        storage = ResumableStorage()
        chunk_storage = storage.get_chunk_storage()
        assert isinstance(chunk_storage, FileSystemStorage)

    def test_get_persistent_storage_default(self):
        """Test that persistent storage defaults appropriately."""
        storage = ResumableStorage()
        persistent_storage = storage.get_persistent_storage()
        # Should return some storage instance
        assert hasattr(persistent_storage, "save")
        assert hasattr(persistent_storage, "delete")

    @override_settings(
        ADMIN_RESUMABLE_STORAGE="django.core.files.storage.FileSystemStorage"
    )
    def test_get_persistent_storage_custom(self):
        """Test persistent storage with custom setting."""
        storage = ResumableStorage()
        persistent_storage = storage.get_persistent_storage()
        assert isinstance(persistent_storage, FileSystemStorage)

    def test_full_filename_with_string_upload_to(self):
        """Test full_filename generation with string upload_to."""
        storage = ResumableStorage()
        filename = storage.full_filename("test.txt", "uploads/%Y/%m/%d", instance=None)

        # Should contain the filename and have path structure
        assert "test.txt" in filename
        assert "/" in filename

    def test_full_filename_with_callable_upload_to(self):
        """Test full_filename generation with callable upload_to."""

        def custom_upload_to(instance, filename):
            return f"custom/{filename}"

        storage = ResumableStorage()
        mock_instance = Mock()
        filename = storage.full_filename(
            "test.txt", custom_upload_to, instance=mock_instance
        )

        assert "custom" in filename
        assert "test.txt" in filename

    @override_settings(
        DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage"
    )
    def test_persistent_storage_respects_default_file_storage(self):
        """Test that persistent storage uses DEFAULT_FILE_STORAGE when ADMIN_RESUMABLE_STORAGE is not set."""
        storage = ResumableStorage()
        persistent_storage = storage.get_persistent_storage()
        assert isinstance(persistent_storage, FileSystemStorage)

    def test_chunk_storage_always_defaults_to_filesystem(self):
        """
        Test that chunk storage always defaults to FileSystemStorage,
        even if default storage is configured differently.
        This ensures chunks are written locally for performance.
        """
        storage = ResumableStorage()
        chunk_storage = storage.get_chunk_storage()
        # Should always be FileSystemStorage by default, not following default storage
        assert isinstance(chunk_storage, FileSystemStorage)

    @patch("django_resumable_async_upload.storage.storages", None)
    def test_get_chunk_storage_older_django(self):
        """Test chunk storage behavior with older Django (no storages API)."""
        storage = ResumableStorage()
        chunk_storage = storage.get_chunk_storage()
        assert isinstance(chunk_storage, FileSystemStorage)

    @patch("django_resumable_async_upload.storage.storages", None)
    def test_get_persistent_storage_older_django(self):
        """Test persistent storage behavior with older Django (no storages API)."""
        storage = ResumableStorage()
        persistent_storage = storage.get_persistent_storage()
        assert hasattr(persistent_storage, "save")

    def test_multiple_storage_instances_independent(self):
        """Test that multiple ResumableStorage instances are independent."""
        storage1 = ResumableStorage()
        storage2 = ResumableStorage()

        chunk1 = storage1.get_chunk_storage()
        chunk2 = storage2.get_chunk_storage()

        # Should be different instances
        assert chunk1 is not chunk2

    def test_storage_methods_exist(self):
        """Test that storage instances have required methods."""
        storage = ResumableStorage()

        chunk_storage = storage.get_chunk_storage()
        assert hasattr(chunk_storage, "save")
        assert hasattr(chunk_storage, "delete")
        assert hasattr(chunk_storage, "exists")
        assert hasattr(chunk_storage, "listdir")
        assert hasattr(chunk_storage, "size")

        persistent_storage = storage.get_persistent_storage()
        assert hasattr(persistent_storage, "save")
        assert hasattr(persistent_storage, "delete")
        assert hasattr(persistent_storage, "exists")
        assert hasattr(persistent_storage, "url")
