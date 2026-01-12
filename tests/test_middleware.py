import pytest
from unittest.mock import Mock, patch

from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from admin_async_upload.middleware import (
    OrphanedFileCleanupMiddleware,
    SESSION_UPLOADED_FILES_KEY,
)
from admin_async_upload.utils import remove_file_from_cleanup_list, clear_cleanup_list


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def middleware():
    """Create middleware instance with a mock get_response."""
    def get_response(request):
        return Mock(status_code=200)
    
    return OrphanedFileCleanupMiddleware(get_response)


@pytest.fixture
def request_with_session(request_factory):
    """Create a request with session support."""
    request = request_factory.get('/')
    
    session_middleware = SessionMiddleware(lambda r: Mock())
    session_middleware.process_request(request)
    request.session.save()
    
    return request


def add_session_to_request(request):
    """Helper to add session to any request."""
    session_middleware = SessionMiddleware(lambda r: Mock())
    session_middleware.process_request(request)
    request.session.save()
    return request


@pytest.mark.django_db
class TestOrphanedFileCleanupMiddleware:
    """Test the orphaned file cleanup middleware."""
    
    def test_no_cleanup_on_post_request(self, middleware, request_factory):
        """Test that files are NOT cleaned up on POST requests."""
        request = add_session_to_request(request_factory.post('/admin/foo/add/'))
        
        test_file_path = 'test_uploads/test_file.txt'
        request.session[SESSION_UPLOADED_FILES_KEY] = [test_file_path]
        request.session.save()
        
        default_storage.save(test_file_path, ContentFile(b'test content'))
        
        try:
            middleware(request)
            
            assert default_storage.exists(test_file_path)
            assert test_file_path in request.session[SESSION_UPLOADED_FILES_KEY]
        finally:
            if default_storage.exists(test_file_path):
                default_storage.delete(test_file_path)
    
    def test_cleanup_on_get_request(self, middleware, request_factory):
        """Test that files ARE cleaned up on GET requests."""
        request = add_session_to_request(request_factory.get('/admin/'))
        
        test_file_path = 'test_uploads/test_file.txt'
        request.session[SESSION_UPLOADED_FILES_KEY] = [test_file_path]
        request.session.save()
        
        default_storage.save(test_file_path, ContentFile(b'test content'))
        
        assert default_storage.exists(test_file_path)
        
        middleware(request)
        
        assert not default_storage.exists(test_file_path)
        assert SESSION_UPLOADED_FILES_KEY not in request.session
    
    def test_no_cleanup_on_upload_request(self, middleware, request_factory):
        """Test that files are NOT cleaned up during upload requests."""
        request = add_session_to_request(request_factory.get('/admin_resumable/'))
        
        test_file_path = 'test_uploads/test_file.txt'
        request.session[SESSION_UPLOADED_FILES_KEY] = [test_file_path]
        request.session.save()
        
        default_storage.save(test_file_path, ContentFile(b'test content'))
        
        try:
            middleware(request)
        
            assert default_storage.exists(test_file_path)
            assert test_file_path in request.session[SESSION_UPLOADED_FILES_KEY]
        finally:
            if default_storage.exists(test_file_path):
                default_storage.delete(test_file_path)
    
    def test_cleanup_multiple_files(self, middleware, request_factory):
        """Test that multiple orphaned files are cleaned up."""
        request = add_session_to_request(request_factory.get('/admin/'))
        
        test_files = [
            'test_uploads/file1.txt',
            'test_uploads/file2.txt',
            'test_uploads/file3.txt',
        ]
        request.session[SESSION_UPLOADED_FILES_KEY] = test_files[:]
        request.session.save()
        
        for file_path in test_files:
            default_storage.save(file_path, ContentFile(b'test content'))
        
        for file_path in test_files:
            assert default_storage.exists(file_path)
        
        middleware(request)
        
        for file_path in test_files:
            assert not default_storage.exists(file_path)
        
        assert SESSION_UPLOADED_FILES_KEY not in request.session
    
    def test_cleanup_handles_missing_files(self, middleware, request_factory):
        """Test that cleanup handles files that don't exist gracefully."""
        request = add_session_to_request(request_factory.get('/admin/'))
        
        # Add files to session, but don't create them
        test_files = [
            'test_uploads/nonexistent1.txt',
            'test_uploads/nonexistent2.txt',
        ]
        request.session[SESSION_UPLOADED_FILES_KEY] = test_files[:]
        request.session.save()
        
        middleware(request)
        
        # Session list should be cleared
        assert SESSION_UPLOADED_FILES_KEY not in request.session
    
    def test_cleanup_partial_failure(self, middleware, request_factory):
        """Test cleanup when some files fail to delete."""
        request = add_session_to_request(request_factory.get('/admin/'))
        
        test_file_path = 'test_uploads/test_file.txt'
        request.session[SESSION_UPLOADED_FILES_KEY] = [test_file_path]
        request.session.save()
        
        default_storage.save(test_file_path, ContentFile(b'test content'))
        
        with patch.object(default_storage, 'delete', side_effect=Exception('Delete failed')):
            middleware(request)
        
        # File should still exist
        assert default_storage.exists(test_file_path)
        
        # File should still be in session because the deletion failed
        assert test_file_path in request.session.get(SESSION_UPLOADED_FILES_KEY, [])
        
        default_storage.delete(test_file_path)
    
    def test_no_cleanup_empty_session(self, middleware, request_factory):
        """Test that middleware handles empty session gracefully."""
        request = add_session_to_request(request_factory.get('/admin/'))
        
        assert SESSION_UPLOADED_FILES_KEY not in request.session
        
        middleware(request)
        
        # Key should still not be in session
        assert SESSION_UPLOADED_FILES_KEY not in request.session
    
    def test_is_upload_request_detection(self, middleware):
        """Test that upload requests are correctly identified."""
        upload_request = Mock(path='/admin_resumable/')
        non_upload_request = Mock(path='/admin/foo/add/')
        
        assert middleware._is_upload_request(upload_request) is True
        assert middleware._is_upload_request(non_upload_request) is False
    
    def test_cleanup_only_removes_existing_files(self, middleware, request_factory):
        """Test that cleanup only removes files that exist in storage."""
        request = add_session_to_request(request_factory.get('/admin/'))
        
        existing_file = 'test_uploads/exists.txt'
        missing_file = 'test_uploads/missing.txt'
        
        request.session[SESSION_UPLOADED_FILES_KEY] = [existing_file, missing_file]
        request.session.save()
        
        default_storage.save(existing_file, ContentFile(b'test content'))
        
        assert default_storage.exists(existing_file)
        assert not default_storage.exists(missing_file)
        
        middleware(request)
        
        assert not default_storage.exists(existing_file)
        assert not default_storage.exists(missing_file)
        assert SESSION_UPLOADED_FILES_KEY not in request.session

@pytest.mark.django_db
class TestUtilityFunctions:
    """Test cleanup utility functions."""
    
    def test_remove_file_from_cleanup_list(self, request_with_session):
        """Test removing a single file from cleanup list."""
        request = request_with_session
        
        test_files = ['file1.txt', 'file2.txt', 'file3.txt']
        request.session[SESSION_UPLOADED_FILES_KEY] = test_files[:]
        request.session.save()
        
        remove_file_from_cleanup_list(request, 'file2.txt')
        
        remaining = request.session[SESSION_UPLOADED_FILES_KEY]
        assert 'file1.txt' in remaining
        assert 'file2.txt' not in remaining
        assert 'file3.txt' in remaining
    
    def test_remove_nonexistent_file(self, request_with_session):
        """Test removing a file that's not in the list."""
        request = request_with_session
        
        test_files = ['file1.txt', 'file2.txt']
        request.session[SESSION_UPLOADED_FILES_KEY] = test_files[:]
        request.session.save()
        
        remove_file_from_cleanup_list(request, 'nonexistent.txt')
        
        remaining = request.session[SESSION_UPLOADED_FILES_KEY]
        assert 'file1.txt' in remaining
        assert 'file2.txt' in remaining
    
    def test_clear_cleanup_list(self, request_with_session):
        """Test clearing entire cleanup list."""
        request = request_with_session
        
        test_files = ['file1.txt', 'file2.txt', 'file3.txt']
        request.session[SESSION_UPLOADED_FILES_KEY] = test_files[:]
        request.session.save()
        
        clear_cleanup_list(request)
        
        assert SESSION_UPLOADED_FILES_KEY not in request.session
    
    def test_clear_empty_list(self, request_with_session):
        """Test clearing when no files are tracked."""
        request = request_with_session
        
        assert SESSION_UPLOADED_FILES_KEY not in request.session
        
        clear_cleanup_list(request)
        
        assert SESSION_UPLOADED_FILES_KEY not in request.session
    
    def test_remove_with_no_session(self):
        """Test that functions handle requests without sessions gracefully."""
        request = Mock(spec=[])  # Request without session attribute
        
        remove_file_from_cleanup_list(request, 'file.txt')
        clear_cleanup_list(request)
