from .models import Foo

from django.test import client as client_module
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

import os
import pytest
import time


def create_test_file(file_path, size_in_megabytes):
    with open(file_path, "wb") as bigfile:
        bigfile.seek(size_in_megabytes * 1024 * 1024)
        bigfile.write(b"0")


def clear_uploads():
    upload_path = os.path.join(settings.MEDIA_ROOT, "admin_uploaded")
    if not os.path.exists(upload_path):
        return
    for the_file in os.listdir(upload_path):
        file_path = os.path.join(upload_path, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(e)


@pytest.mark.django_db
def test_fake_file_upload(admin_user, admin_client):
    foo_ct = ContentType.objects.get_for_model(Foo)
    clear_uploads()

    payload = client_module.FakePayload()

    def form_value_list(key, value):
        return [
            "--" + client_module.BOUNDARY,
            'Content-Disposition: form-data; name="%s"' % key,
            "",
            value,
        ]

    form_vals = []
    file_data = "foo bar foo bar."
    file_size = str(len(file_data))
    form_vals += form_value_list("resumableChunkNumber", "1")
    form_vals += form_value_list("resumableCurrentChunkSize", file_size)
    form_vals += form_value_list("resumableChunkSize", file_size)
    form_vals += form_value_list("resumableType", "text/plain")
    form_vals += form_value_list("resumableIdentifier", file_size + "-foobar")
    form_vals += form_value_list("resumableFilename", "foo.bar")
    form_vals += form_value_list("resumableTotalChunks", "1")
    form_vals += form_value_list("resumableTotalSize", file_size)
    form_vals += form_value_list("content_type_id", str(foo_ct.id))
    form_vals += form_value_list("field_name", "foo")
    payload.write(
        "\r\n".join(
            form_vals
            + [
                "--" + client_module.BOUNDARY,
                'Content-Disposition: form-data; name="file"; filename=foo.bar',
                "Content-Type: application/octet-stream",
                "",
                file_data,
                "--" + client_module.BOUNDARY + "--\r\n",
            ]
        )
    )

    r = {
        "CONTENT_LENGTH": len(payload),
        "CONTENT_TYPE": client_module.MULTIPART_CONTENT,
        "PATH_INFO": "/admin_resumable/upload/",
        "REQUEST_METHOD": "POST",
        "wsgi.input": payload,
    }
    response = admin_client.request(**r)
    assert response.status_code == 200
    upload_filename = file_size + "_foo.bar"
    upload_path = os.path.join(settings.MEDIA_ROOT, upload_filename)
    f = open(upload_path, "r")
    uploaded_contents = f.read()
    assert file_data == uploaded_contents


@pytest.mark.django_db
def test_fake_file_upload_incomplete_chunk(admin_user, admin_client):
    foo_ct = ContentType.objects.get_for_model(Foo)
    clear_uploads()

    payload = client_module.FakePayload()

    def form_value_list(key, value):
        return [
            "--" + client_module.BOUNDARY,
            'Content-Disposition: form-data; name="%s"' % key,
            "",
            value,
        ]

    form_vals = []
    file_data = "foo bar foo bar."
    file_size = str(len(file_data))
    form_vals += form_value_list("resumableChunkNumber", "1")
    form_vals += form_value_list("resumableChunkSize", "3")
    form_vals += form_value_list("resumableType", "text/plain")
    form_vals += form_value_list("resumableIdentifier", file_size + "-foobar")
    form_vals += form_value_list("resumableFilename", "foo.bar")
    form_vals += form_value_list("resumableTotalChunks", "6")
    form_vals += form_value_list("resumableTotalSize", file_size)
    form_vals += form_value_list("content_type_id", str(foo_ct.id))
    form_vals += form_value_list("field_name", "foo")
    payload.write(
        "\r\n".join(
            form_vals
            + [
                "--" + client_module.BOUNDARY,
                'Content-Disposition: form-data; name="file"; filename=foo.bar',
                "Content-Type: application/octet-stream",
                "",
                file_data[0:1],
                # missing final boundary to simulate failure
            ]
        )
    )

    r = {
        "CONTENT_LENGTH": len(payload),
        "CONTENT_TYPE": client_module.MULTIPART_CONTENT,
        "PATH_INFO": "/admin_resumable/admin_resumable/",
        "REQUEST_METHOD": "POST",
        "wsgi.input": payload,
    }
    try:
        admin_client.request(**r)
    except AttributeError:
        pass  # we're not worried that this would 500

    get_url = "/admin_resumable/admin_resumable/?"
    get_args = {
        "resumableChunkNumber": "1",
        "resumableChunkSize": "3",
        "resumableCurrentChunkSize": "3",
        "resumableTotalSize": file_size,
        "resumableType": "text/plain",
        "resumableIdentifier": file_size + "-foobar",
        "resumableFilename": "foo.bar",
        "resumableRelativePath": "foo.bar",
        "content_type_id": str(foo_ct.id),
        "field_name": "foo",
    }

    # we need a fresh client because client.request breaks things
    fresh_client = client_module.Client()
    fresh_client.login(username=admin_user.username, password="password")
    get_response = fresh_client.get(get_url, get_args)
    # should be a 404 because we uploaded an incomplete chunk
    assert get_response.status_code == 404

@pytest.mark.django_db
def test_real_file_upload(admin_user, live_server, page):
    test_file_path = "/tmp/test_small_file_success.bin"
    # Clean up any existing test file from prior runs just in case
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    create_test_file(test_file_path, 5)

    page.goto(live_server.url + "/admin/")
    
    # Wait for login page to load and fill in credentials
    page.wait_for_selector("#id_username")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "password")
    page.click('input[value="Log in"]')
    
    # Wait for successful login - check that we're no longer on the login page
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10000)
    
    # Verify we can see the admin dashboard (session is working)
    page.wait_for_selector("#content")
    
    # Add extra wait to ensure session cookie is fully set
    time.sleep(2)
    
    page.goto(live_server.url + "/admin/tests/foo/add/")
    page.wait_for_selector("#id_foo_input_file", timeout=15000)
    page.set_input_files("#id_foo_input_file", test_file_path)

    try:
        # Wait for at least one file-status element to appear
        page.wait_for_selector(".file-status", timeout=15000)
        
        # Wait for the upload to complete by checking for "Uploaded" or "✓" in the status
        page.wait_for_function("""
            () => {
                const elements = document.querySelectorAll('.file-status');
                return Array.from(elements).some(elem => 
                    elem.textContent.includes('Uploaded') || elem.textContent.includes('✓')
                );
            }
        """, timeout=20000)
        
        # Verify the upload completed successfully
        status_elements = page.locator(".file-status").all()
        status_texts = [elem.text_content() for elem in status_elements]
        assert any("Uploaded" in text or "✓" in text for text in status_texts), \
            f"No file status contains 'Uploaded' or '✓'. Found: {status_texts}"
        
    except Exception as e:
        # Print page content for debugging
        print("Page source:", page.content())
        print("Console logs:", page.evaluate("() => console.log('Debug info')"))
        
        raise
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

@pytest.mark.django_db
def test_real_file_upload_multiple(admin_user, live_server, page):
    test_file_path_1 = "/tmp/test_small_file_1.bin"
    test_file_path_2 = "/tmp/test_small_file_2.bin"
    # Clean up any existing test file from prior runs just in case
    if os.path.exists(test_file_path_1):
        os.unlink(test_file_path_1)
    if os.path.exists(test_file_path_2):
        os.unlink(test_file_path_2) 
    create_test_file(test_file_path_1, 5)
    create_test_file(test_file_path_2, 5)

    page.goto(live_server.url + "/admin/")
    
    # Wait for login page and fill credentials
    page.wait_for_selector("#id_username")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "password")
    page.click('input[value="Log in"]')
    
    # Wait for successful login
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10000)
    page.wait_for_selector("#content")
    time.sleep(2)
    
    page.goto(live_server.url + "/admin/tests/foo/add/")
    page.wait_for_selector("#id_bar")
    page.fill("#id_bar", "bat")
    
    # Wait for file input and upload multiple files
    page.wait_for_selector("#id_foo_input_file")
    time.sleep(1)
    page.set_input_files("#id_foo_input_file", [test_file_path_1, test_file_path_2])

    try:
        # Wait for file-status elements
        page.wait_for_selector(".file-status", timeout=15000)
        
        # Wait for uploads to complete
        page.wait_for_function("""
            () => {
                const elements = document.querySelectorAll('.file-status');
                return Array.from(elements).some(elem => 
                    elem.textContent.includes('Uploaded') || elem.textContent.includes('✓')
                );
            }
        """, timeout=20000)
        
        # Verify uploads completed successfully
        status_elements = page.locator(".file-status").all()
        status_texts = [elem.text_content() for elem in status_elements]
        
        assert any("Uploaded" in text or "✓" in text for text in status_texts), \
            f"No file status contains 'Uploaded' or '✓'. Found: {status_texts}"
        assert len(status_elements) == 2, f"Expected 2 file-status elements, found {len(status_elements)}"

    except Exception as e:
        print("Page source:", page.content())
        raise
    finally:
        if os.path.exists(test_file_path_1):
            os.unlink(test_file_path_1)
        if os.path.exists(test_file_path_2):
            os.unlink(test_file_path_2)


@pytest.mark.django_db
def test_real_file_upload_cancel_single_file(admin_user, live_server, page):
    test_file_path = "/tmp/test_small_file_cancel.bin"
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    create_test_file(test_file_path, 5)

    page.goto(live_server.url + "/admin/")
    page.wait_for_selector("#id_username")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "password")
    page.click('input[value="Log in"]')
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10000)
    page.wait_for_selector("#content")
    time.sleep(2)
    
    page.goto(live_server.url + "/admin/tests/foo/add/")
    page.wait_for_selector("#id_foo_input_file", timeout=15000)
    page.set_input_files("#id_foo_input_file", test_file_path)

    try:
        # Wait for file-status element
        page.wait_for_selector(".file-status", timeout=20000)
        
        # Wait for upload to start
        page.wait_for_function("""
            () => {
                const progress = document.querySelector('.file-progress');
                return progress && parseFloat(progress.value) > 0;
            }
        """, timeout=15000)

        # Click cancel button
        cancel_button = page.locator(".file-cancel-btn").first
        cancel_button.wait_for(state="visible", timeout=10000)
        cancel_button.click()
        
        time.sleep(2)
        
        # Verify cancellation
        status_elements = page.locator(".file-status").all()
        status_texts = [elem.text_content() for elem in status_elements]
        
        assert all("Uploaded" not in text and "✓" not in text for text in status_texts)
        assert len(status_elements) == 0, f"Expected 0 file-status elements after cancellation, found {len(status_elements)}"
    except Exception as e:
        print("Page source:", page.content())
        raise
    finally:
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

@pytest.mark.django_db
def test_real_file_upload_cancel_all_files(admin_user, live_server, page):
    test_file_path = "/tmp/test_large_file_cancel_all.bin"
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    create_test_file(test_file_path, 50)

    page.goto(live_server.url + "/admin/")
    page.wait_for_selector("#id_username")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "password")
    page.click('input[value="Log in"]')
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10000)
    page.wait_for_selector("#content")
    time.sleep(2)
    
    page.goto(live_server.url + "/admin/tests/foo/add/")
    page.wait_for_selector("#id_foo_input_file")
    page.set_input_files("#id_foo_input_file", test_file_path)

    try:
        # Wait for cancel button to be clickable
        page.wait_for_selector("#id_foo_cancel", state="visible", timeout=15000)
        page.wait_for_selector(".file-status", timeout=5000)
        
        # Click cancel
        page.click("#id_foo_cancel")
        time.sleep(2)
        
        # Verify no status elements remain
        status_elements = page.locator(".file-status").all()
        assert len(status_elements) == 0, f"Expected 0 file-status elements after cancellation, found {len(status_elements)}"
        
        # Verify controls are hidden
        controls_visible = page.locator("#id_foo_controls").is_visible()
        assert not controls_visible, "Controls element should be hidden after cancelling all uploads"
    except Exception as e:
        print("Page source:", page.content())
        raise
    finally:
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

@pytest.mark.django_db
def test_real_file_upload_pause_resume(admin_user, live_server, page, settings):
    settings.ADMIN_RESUMABLE_CHUNKSIZE = "100*1024"  # 100KB chunks
    test_file_path = "/tmp/test_large_file_cancel_all.bin"
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    create_test_file(test_file_path, 5)

    page.goto(live_server.url + "/admin/")
    page.wait_for_selector("#id_username")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "password")
    page.click('input[value="Log in"]')
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10000)
    page.wait_for_selector("#content")
    time.sleep(2)
    
    page.goto(live_server.url + "/admin/tests/foo/add/")
    page.wait_for_selector("#id_foo_input_file")
    page.set_input_files("#id_foo_input_file", test_file_path)
    
    try:
        # Wait for file-status element
        page.wait_for_selector(".file-status", timeout=15000)
        page.wait_for_selector("#id_foo_pause", state="visible", timeout=10000)

        # Get initial progress
        progress_before_pause = float(page.locator(".file-progress").first.get_attribute("value"))
        assert progress_before_pause > 0, f"Upload has not started. Progress: {progress_before_pause}"

        # Pause upload
        page.click("#id_foo_pause")
        time.sleep(1)
        
        # Get progress after pausing
        progress_during_pause_1 = float(page.locator(".file-progress").first.get_attribute("value"))
        time.sleep(5)
        progress_during_pause_2 = float(page.locator(".file-progress").first.get_attribute("value"))
        
        # Verify progress hasn't increased while paused
        assert abs(progress_during_pause_2 - progress_during_pause_1) < 0.05, \
            f"Upload continued while paused. First: {progress_during_pause_1}, Second: {progress_during_pause_2}"
        
        # Resume upload
        page.click("#id_foo_resume")
        
        # Wait for completion
        page.wait_for_function("""
            () => {
                const elements = document.querySelectorAll('.file-status');
                return Array.from(elements).some(elem => 
                    elem.textContent.includes('Uploaded') || elem.textContent.includes('✓')
                );
            }
        """, timeout=20000)
        
        progress_after_resume = float(page.locator(".file-progress").first.get_attribute("value"))
        
        # Verify progress after resume
        assert progress_after_resume > progress_during_pause_2, \
            f"Upload did not progress after resume. During pause: {progress_during_pause_2}, After: {progress_after_resume}"
        assert progress_after_resume == 1.0, \
            f"Upload did not complete after resume. Final progress: {progress_after_resume}"

    except Exception as e:
        print("Page source:", page.content())
        raise
    finally:
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

def test_real_file_upload_file_error(admin_user, live_server, page):
    test_file_path = "/tmp/test_failed_file.bin"
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    create_test_file(test_file_path, 5)

    page.goto(live_server.url + "/admin/")
    page.wait_for_selector("#id_username")
    page.fill("#id_username", "admin")
    page.fill("#id_password", "password")
    page.click('input[value="Log in"]')
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10000)
    page.wait_for_selector("#content")
    time.sleep(2)
    
    page.goto(live_server.url + "/admin/tests/foo/add/")
    page.wait_for_selector("#id_bar")
    page.fill("#id_bar", "bat")
    
    # Inject JavaScript to mock error response
    page.evaluate("""
        (function() {
            var OriginalXHR = window.XMLHttpRequest;
            window.XMLHttpRequest = function() {
                var xhr = new OriginalXHR();
                var originalOpen = xhr.open;
                var originalSend = xhr.send;
                
                xhr.open = function(method, url) {
                    this._method = method;
                    this._url = url;
                    return originalOpen.apply(this, arguments);
                };
                
                xhr.send = function(data) {
                    var self = this;
                    
                    if (this._method === 'POST' && this._url.includes('admin_resumable')) {
                        setTimeout(function() {
                            Object.defineProperty(self, 'status', { 
                                writable: true, 
                                configurable: true,
                                value: 500 
                            });
                            Object.defineProperty(self, 'readyState', { 
                                writable: true, 
                                configurable: true,
                                value: 4 
                            });
                            Object.defineProperty(self, 'responseText', { 
                                writable: true, 
                                configurable: true,
                                value: 'Internal Server Error' 
                            });
            
                            var event = new Event('load');
                            
                            if (self.onreadystatechange) {
                                self.onreadystatechange(event);
                            }
                            if (self.onload) {
                                self.onload(event);
                            }
                            
                            self.dispatchEvent(event);
                        }, 100);
                        return;
                    }
                    return originalSend.call(this, data);
                };
                
                return xhr;
            };
        })();
    """)
    
    # Wait for file input and upload
    page.wait_for_selector("#id_foo_input_file")
    time.sleep(1)
    page.set_input_files("#id_foo_input_file", test_file_path)

    try:
        # Wait for error message in file-status
        page.wait_for_function("""
            () => {
                const elements = document.querySelectorAll('.file-status');
                return Array.from(elements).some(elem => 
                    elem.textContent.includes('Error')
                );
            }
        """, timeout=20000)
        
        # Verify error message is displayed
        status_elements = page.locator(".file-status").all()
        status_texts = [elem.text_content() for elem in status_elements]

        assert any("Error" in text for text in status_texts), \
            f"No file status contains 'Error'. Found: {status_texts}"
        
    except Exception as e:
        print("Page source:", page.content())
        raise
    finally:
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

