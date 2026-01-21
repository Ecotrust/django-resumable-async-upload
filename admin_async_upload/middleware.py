# TODO: allow for getting storage from settings
from django.core.files.storage import default_storage


SESSION_UPLOADED_FILES_KEY = 'admin_resumable_uploaded_files'


class OrphanedFileCleanupMiddleware:
    """
    Middleware that cleans up uploaded files that were never saved to a model instance.
    Files are tracked in the session and cleaned up when the user navigates away.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Only clean up orphaned files when truly navigating away from the form
        # NOT on POST requests (might be saving)
        # NOT on GET requests that are part of form editing (popups, autocomplete, etc.)
        if request.method == 'GET' and self._should_cleanup(request):
            self._cleanup_orphaned_files(request)
            
        return response
    
    def _is_upload_request(self, request):
        """Check if this is an AJAX upload request (not a form save)."""
        # Check for both possible URL patterns (admin_resumable or admin_async_upload)
        return 'admin_resumable' in request.path or 'admin_async_upload/upload' in request.path
    
    def _should_cleanup(self, request):
        """
        Determine if we should cleanup orphaned files.
        Only cleanup when user is truly leaving the form, not during form editing.
        """
        current_path = request.path
        
        # Don't cleanup during upload requests
        if self._is_upload_request(request):
            return False
        
        # Don't cleanup for AJAX requests (autocomplete, etc.)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return False
        
        # Don't cleanup if there are no files to cleanup
        if not request.session.get(SESSION_UPLOADED_FILES_KEY):
            return False
        
        # Don't cleanup for Django admin utility endpoints
        admin_utility_paths = [
            '/jsi18n/',
            '/autocomplete/',
            '/select2/',
            '/__debug__/',
        ]
        if any(path in current_path for path in admin_utility_paths):
            return False
        
        # Don't cleanup if URL has popup parameter
        if '_popup' in request.GET or '_to_field' in request.GET:
            return False
        
        referer = request.META.get('HTTP_REFERER', '')
        
        # If referer contains /add/ or /change/ and current path doesn't,
        # then the user must be navigating away from the form
        if ('/add/' in referer or '/change/' in referer):
            if '/add/' not in current_path and '/change/' not in current_path:
                # User left the form without saving
                return True
            else:
                # Still on a form page (might be a popup or related form such as adding a related record)
                return False
        
        # If no clear referer pattern, don't cleanup (be conservative)
        return False
    
    def _cleanup_orphaned_files(self, request):
        """
        Clean up files that are still in the session after navigating away.
        This happens when user uploads a file but navigates away without saving
        """
        orphaned_files = request.session.get(SESSION_UPLOADED_FILES_KEY, [])
        if orphaned_files:
            storage = default_storage
            # Copy the list to avoid issues during iteration
            files_to_delete = orphaned_files.copy()
            for file_path in files_to_delete:
                try:
                    if storage.exists(file_path):
                        storage.delete(file_path)
                except Exception as e:
                    return
            
            request.session.pop(SESSION_UPLOADED_FILES_KEY, None)
            request.session.modified = True
