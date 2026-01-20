from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from django.utils.functional import cached_property
from django.views.generic import View
from admin_async_upload.files import ResumableFile
from django.contrib.sessions.models import Session
from django.core.files.storage import default_storage
import threading
import json


SESSION_UPLOADED_FILES_KEY = 'admin_resumable_uploaded_files'

# Thread lock to prevent race conditions when multiple files upload simultaneously
_session_lock = threading.Lock()


class UploadView(View):
    # inspired by another fork https://github.com/fdemmer/django-admin-resumable-js

    @cached_property
    def request_data(self):
        return getattr(self.request, self.request.method)

    @cached_property
    def model_upload_field(self):
        content_type = ContentType.objects.get_for_id(self.request_data['content_type_id'])
        return content_type.model_class()._meta.get_field(self.request_data['field_name'])

    def post(self, request, *args, **kwargs):
        chunk = request.FILES.get('file')
        r = ResumableFile(self.model_upload_field, user=request.user, params=request.POST)
        if not r.chunk_exists:
            r.process_chunk(chunk)
        if r.is_complete:
            file_path = r.collect()
            # Track uploaded file in session for potential cleanup
            self._track_uploaded_file(request, file_path)
            return HttpResponse(file_path)
        return HttpResponse('chunk uploaded')

    def get(self, request, *args, **kwargs):
        r = ResumableFile(self.model_upload_field, user=request.user, params=request.GET)
        if not r.chunk_exists:
            return HttpResponse('chunk not found', status=204)
        if r.is_complete:
            return HttpResponse(r.collect())
        return HttpResponse('chunk exists')
    
    def delete(self, request, *args, **kwargs):
        """Handle file deletion via DELETE request."""
        try:
            # Parse the file path from request body
            body = json.loads(request.body.decode('utf-8'))
            file_path = body.get('file_path')
            
            if not file_path:
                return JsonResponse({'error': 'file_path required'}, status=400)
            
            # Delete from storage
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
            
            # Remove from session tracking
            self._remove_from_tracking(request, file_path)
            
            return JsonResponse({'status': 'success', 'message': 'File removed'})
        except Exception as e:
            print(f"[ERROR]: Failed to delete file: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def _remove_from_tracking(self, request, file_path):
        """Remove a file from session tracking."""
        with _session_lock:
            if SESSION_UPLOADED_FILES_KEY in request.session:
                tracked_files = request.session[SESSION_UPLOADED_FILES_KEY]
                if file_path in tracked_files:
                    tracked_files.remove(file_path)
                    request.session[SESSION_UPLOADED_FILES_KEY] = tracked_files
                    request.session.modified = True
                    request.session.save()
                    return HttpResponse('file removed')
        return HttpResponse('file not found', status=404)

    def _track_uploaded_file(self, request, file_path):
        """Track uploaded files in session for cleanup if form is not saved."""
        # Use thread lock to prevent race conditions when multiple files upload simultaneously
        with _session_lock:
            # Ensure session is loaded and has a session key
            if not request.session.session_key:
                request.session.create()
            
            session_key = request.session.session_key
            
            # Force reload from database by getting a fresh session instance
            try:
                session_obj = Session.objects.get(session_key=session_key)
                session_data = session_obj.get_decoded()
            except Session.DoesNotExist:
                session_data = {}
            
            # Get or initialize the tracked files list from fresh data
            tracked_files = session_data.get(SESSION_UPLOADED_FILES_KEY, [])
            
            if file_path not in tracked_files:
                tracked_files.append(file_path)
                # Update the session with new data
                request.session[SESSION_UPLOADED_FILES_KEY] = tracked_files
                request.session.modified = True
                # Force save to ensure persistence across multiple uploads
                request.session.save()
            else:
                print("File already tracked:", file_path)


admin_resumable = login_required(UploadView.as_view())
