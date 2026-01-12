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
        return 'admin_resumable' in request.path
    
    def _should_cleanup(self, request):
        """
        Determine if we should cleanup orphaned files.
        Only cleanup when user is truly leaving the form, not during form editing.
        """
        # Don't cleanup during upload requests
        if self._is_upload_request(request):
            print('Not cleaning up: upload request')
            return False
        
        # Don't cleanup for AJAX requests (autocomplete, etc.)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            print('Not cleaning up: AJAX request')
            return False
        
        # Don't cleanup if there are no files to cleanup
        if not request.session.get(SESSION_UPLOADED_FILES_KEY):
            print('Not cleaning up: no files to cleanup')
            return False
        
        current_path = request.path
        
        # Don't cleanup for Django admin utility endpoints
        admin_utility_paths = [
            '/jsi18n/',
            '/autocomplete/',
            '/select2/',
            '/__debug__/',
        ]
        if any(path in current_path for path in admin_utility_paths):
            print('Not cleaning up: admin utility path')
            return False
        
        # Don't cleanup if URL has popup parameter
        if '_popup' in request.GET or '_to_field' in request.GET:
            print('Not cleaning up: popup or to_field parameter')
            return False
        
        referer = request.META.get('HTTP_REFERER', '')
        
        # If referer contains /add/ or /change/ and current path doesn't,
        # then the user must be navigating away from the form
        print(f"Referer: {referer}, Current Path: {current_path}")
        if ('/add/' in referer or '/change/' in referer):
            if '/add/' not in current_path and '/change/' not in current_path:
                # User left the form without saving
                print('Cleaning up: navigated away from form')
                return True
            else:
                # Still on a form page (might be a popup or related form such as adding a related record)
                print('Not cleaning up: still on form page')
                return False
        
        # If no clear referer pattern, don't cleanup (be conservative)
        print('Not cleaning up: no clear referer pattern')
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
            files_to_delete = orphaned_files[:]
            for file_path in files_to_delete:
                try:
                    if storage.exists(file_path):
                        storage.delete(file_path)
                except Exception as e:
                    return
            
            request.session.pop(SESSION_UPLOADED_FILES_KEY, None)
            request.session.modified = True
