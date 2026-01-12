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
        
        # Only clean up orphaned files on GET requests (navigation away)
        # NOT on POST requests, as those might be saving the form
        # The form's save method will remove saved files from the list during POST
        # TODO: need to allow for GET requests that happen while editing the form. This is too permissive. 
        if request.method == 'GET' and not self._is_upload_request(request):
            self._cleanup_orphaned_files(request)
            
        return response
    
    def _is_upload_request(self, request):
        """Check if this is an AJAX upload request (not a form save)."""
        return 'admin_resumable' in request.path
    
    def _cleanup_orphaned_files(self, request):
        """
        Clean up files that are still in the session after navigating away.
        This happens when user uploads a file but navigates away without saving
        """
        orphaned_files = request.session.get(SESSION_UPLOADED_FILES_KEY, [])
        if orphaned_files:
            storage = default_storage
            # Copy the list to avoid issues during iteration
            files_to_delete = orphaned_files[:]
            for file_path in files_to_delete:
                try:
                    if storage.exists(file_path):
                        storage.delete(file_path)
                except Exception as e:
                    pass
            
            request.session.pop(SESSION_UPLOADED_FILES_KEY, None)
            request.session.modified = True
