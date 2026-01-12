from admin_async_upload.middleware import SESSION_UPLOADED_FILES_KEY


def remove_file_from_cleanup_list(request, file_path):
    """
    Remove a file from the cleanup list in the session.
    Call this when a file has been successfully saved to a model.
    
    Args:
        request: The current HttpRequest object
        file_path: Path to the file that should not be cleaned up
    """
    if not request or not hasattr(request, 'session'):
        return

    session_files = request.session.get(SESSION_UPLOADED_FILES_KEY, [])
    if file_path in session_files:
        session_files.remove(file_path)
        request.session[SESSION_UPLOADED_FILES_KEY] = session_files
        request.session.modified = True
        request.session.save()


def clear_cleanup_list(request):
    """
    Clear all files from the cleanup list.
    Call this after successfully saving a form with uploaded files.
    
    Args:
        request: The current HttpRequest object
    """
    if not request or not hasattr(request, 'session'):
        return
    
    if SESSION_UPLOADED_FILES_KEY in request.session:
        del request.session[SESSION_UPLOADED_FILES_KEY]
        request.session.modified = True
        request.session.save()
    else:
        return