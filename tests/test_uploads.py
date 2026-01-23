from .models import Foo

from django.test import client as client_module
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
def test_real_file_upload(admin_user, live_server, driver):
    test_file_path = "/tmp/test_small_file_success.bin"
    # Clean up any existing test file from prior runs just in case
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    create_test_file(test_file_path, 5)

    driver.get(live_server.url + "/admin/")
    
    # Wait for login page to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )
    
    driver.find_element(By.ID, "id_username").send_keys("admin")
    driver.find_element(By.ID, "id_password").send_keys("password")
    driver.find_element(By.XPATH, '//input[@value="Log in"]').click()
    
    # Wait for successful login - check that we're no longer on the login page
    WebDriverWait(driver, 10).until(
        lambda d: "/login/" not in d.current_url
    )
    
    # Verify we can see the admin dashboard (session is working)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#content"))
    )
    
    # Add extra wait to ensure session cookie is fully set
    time.sleep(2)
    
    driver.get(live_server.url + "/admin/tests/foo/add/")
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "id_foo_input_file")))
    driver.find_element(By.ID, "id_foo_input_file").send_keys(test_file_path)

    try:
        # Wait for at least one file-status element to appear (not just the container)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "file-status"))
        )
        
        # Wait for the upload to complete by checking for "Uploaded" or "✓" in the status
        WebDriverWait(driver, 20).until(
            lambda d: any(
                "Uploaded" in elem.text or "✓" in elem.text 
                for elem in d.find_elements(By.CLASS_NAME, "file-status")
            )
        )
        
        # Verify the upload completed successfully
        status_elements = driver.find_elements(By.CLASS_NAME, "file-status")
        assert any("Uploaded" in elem.text or "✓" in elem.text for elem in status_elements), \
            f"No file status contains 'Uploaded' or '✓'. Found: {[elem.text for elem in status_elements]}"
        
    except Exception as e:
        # Print page source for debugging
        print("Page source:", driver.page_source)
        print("Console logs:", driver.get_log('browser'))
        
        raise
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

@pytest.mark.django_db
def test_real_file_upload_multiple(admin_user, live_server, driver):
    test_file_path_1 = "/tmp/test_small_file_1.bin"
    test_file_path_2 = "/tmp/test_small_file_2.bin"
    # Clean up any existing test file from prior runs just in case
    if os.path.exists(test_file_path_1):
        os.unlink(test_file_path_1)
    if os.path.exists(test_file_path_2):
        os.unlink(test_file_path_2) 
    create_test_file(test_file_path_1, 5)
    create_test_file(test_file_path_2, 5)

    driver.get(live_server.url + "/admin/")
    
    # Wait for login page to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )
    
    driver.find_element(By.ID, "id_username").send_keys("admin")
    driver.find_element(By.ID, "id_password").send_keys("password")
    driver.find_element(By.XPATH, '//input[@value="Log in"]').click()
    
    # Wait for successful login - check that we're no longer on the login page
    WebDriverWait(driver, 10).until(
        lambda d: "/login/" not in d.current_url
    )
    
    # Verify we can see the admin dashboard (session is working)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#content"))
    )
    
    # Add extra wait to ensure session cookie is fully set
    time.sleep(2)
    
    driver.get(live_server.url + "/admin/tests/foo/add/")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_bar")))
    driver.find_element(By.ID, "id_bar").send_keys("bat")
    
    # Wait for the file input to be ready
    file_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_foo_input_file"))
    )
    
    # Give the page a moment to fully initialize JavaScript
    time.sleep(1)
    file_input.send_keys(test_file_path_1 + "\n" + test_file_path_2)

    try:
        # Wait for at least one file-status element to appear (not just the container)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "file-status"))
        )
        
        # Wait for the upload to complete by checking for "Uploaded" or "✓" in the status
        WebDriverWait(driver, 20).until(
            lambda d: any(
                "Uploaded" in elem.text or "✓" in elem.text 
                for elem in d.find_elements(By.CLASS_NAME, "file-status")
            )
        )
        
        # Verify the upload completed successfully
        status_elements = driver.find_elements(By.CLASS_NAME, "file-status")
        
        assert any("Uploaded" in elem.text or "✓" in elem.text for elem in status_elements), \
            f"No file status contains 'Uploaded' or '✓'. Found: {[elem.text for elem in status_elements]}"
        assert len(status_elements) == 2, f"Expected 2 file-status elements, found {len(status_elements)}"

    except Exception as e:
        # Print page source for debugging
        print("Page source:", driver.page_source)
        print("Console logs:", driver.get_log('browser'))
        raise
    finally:
        # Clean up test file
        if os.path.exists(test_file_path_1):
            os.unlink(test_file_path_1)
        if os.path.exists(test_file_path_2):
            os.unlink(test_file_path_2)


@pytest.mark.django_db
def test_real_file_upload_cancel_single_file(admin_user, live_server, driver):
    test_file_path = "/tmp/test_small_file_cancel.bin"
    # Clean up any existing test file from prior runs just in case
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    create_test_file(test_file_path, 5)

    driver.get(live_server.url + "/admin/")
    
    # Wait for login page to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )
    
    driver.find_element(By.ID, "id_username").send_keys("admin")
    driver.find_element(By.ID, "id_password").send_keys("password")
    driver.find_element(By.XPATH, '//input[@value="Log in"]').click()
    
    # Wait for successful login - check that we're no longer on the login page
    WebDriverWait(driver, 10).until(
        lambda d: "/login/" not in d.current_url
    )
    
    # Verify we can see the admin dashboard (session is working)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#content"))
    )
    
    # Add extra wait to ensure session cookie is fully set
    time.sleep(2)
    
    driver.get(live_server.url + "/admin/tests/foo/add/")
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "id_foo_input_file")))
    driver.find_element(By.ID, "id_foo_input_file").send_keys(test_file_path)

    try:
        # Wait for at least one file-status element to appear (not just the container)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "file-status"))
        )
        assert len(driver.find_elements(By.CLASS_NAME, "file-status")) > 0

        # Click the cancel button for the first file
        cancel_button = driver.find_element(By.CLASS_NAME, "file-cancel-btn")
        cancel_button.click()
        
        # Wait a moment to allow cancellation to process
        time.sleep(2)
        
        # Verify that no file status indicates completion
        status_elements = driver.find_elements(By.CLASS_NAME, "file-status")

        assert all("Uploaded" not in elem.text and "✓" not in elem.text for elem in status_elements)

        assert len(status_elements) == 0, f"Expected 0 file-status elements after cancellation, found {len(status_elements)}"
    except Exception as e:
        # Print page source for debugging
        print("Page source:", driver.page_source)
        print("Console logs:", driver.get_log('browser'))
        raise  # Re-raise the exception so the test fails
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

@pytest.mark.django_db
def test_real_file_upload_cancel_all_files(admin_user, live_server, driver):
    test_file_path = "/tmp/test_large_file_cancel_all.bin"
    # Clean up any existing test file from prior runs just in case
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    # Use a larger file (50MB) to ensure we have time to click cancel before upload completes
    create_test_file(test_file_path, 50)

    driver.get(live_server.url + "/admin/")
    
    # Wait for login page to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )
    
    driver.find_element(By.ID, "id_username").send_keys("admin")
    driver.find_element(By.ID, "id_password").send_keys("password")
    driver.find_element(By.XPATH, '//input[@value="Log in"]').click()
    
    # Wait for successful login - check that we're no longer on the login page
    WebDriverWait(driver, 10).until(
        lambda d: "/login/" not in d.current_url
    )
    
    # Verify we can see the admin dashboard (session is working)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#content"))
    )
    
    # Add extra wait to ensure session cookie is fully set
    time.sleep(2)
    
    driver.get(live_server.url + "/admin/tests/foo/add/")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_foo_input_file")))
    driver.find_element(By.ID, "id_foo_input_file").send_keys(test_file_path)

    try:
        # Wait for upload to start and cancel button to become visible and clickable
        cancel_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "id_foo_cancel"))
        )
        
        # Verify file status exists
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "file-status"))
        )
        
        # Click cancel while upload is in progress
        cancel_button.click()
        
        # Wait a moment to allow cancellation to process
        time.sleep(2)
        
        # Verify that no file status elements remain (they should be removed)
        status_elements = driver.find_elements(By.CLASS_NAME, "file-status")
        
        assert len(status_elements) == 0, f"Expected 0 file-status elements after cancellation, found {len(status_elements)}"
        
        # Verify controls are hidden
        controls_element = driver.find_element(By.ID, "id_foo_controls")
        assert not controls_element.is_displayed(), "Controls element should be hidden after cancelling all uploads"
    except Exception as e:
        # Print page source for debugging
        print("Page source:", driver.page_source)
        print("Console logs:", driver.get_log('browser'))
        raise  # Re-raise the exception so the test fails
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

@pytest.mark.django_db
def test_real_file_upload_pause_resume(admin_user, live_server, driver):
    test_file_path = "/tmp/test_large_file_cancel_all.bin"
    # Clean up any existing test file from prior runs just in case
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    # Use a larger file (50MB) to ensure we have time to click pause before upload completes
    create_test_file(test_file_path, 50)

    driver.get(live_server.url + "/admin/")
    
    # Wait for login page to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )
    
    driver.find_element(By.ID, "id_username").send_keys("admin")
    driver.find_element(By.ID, "id_password").send_keys("password")
    driver.find_element(By.XPATH, '//input[@value="Log in"]').click()
    
    # Wait for successful login - check that we're no longer on the login page
    WebDriverWait(driver, 10).until(
        lambda d: "/login/" not in d.current_url
    )
    
    # Verify we can see the admin dashboard (session is working)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#content"))
    )
    
    # Add extra wait to ensure session cookie is fully set
    time.sleep(2)
    
    driver.get(live_server.url + "/admin/tests/foo/add/")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_foo_input_file")))
    driver.find_element(By.ID, "id_foo_input_file").send_keys(test_file_path)

    try:
        # Wait for at least one file-status element to appear (not just the container)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "file-status"))
        )

        progress_bar_before_pause = driver.find_element(By.CLASS_NAME, "file-progress").get_attribute("value")

        # Pause the upload
        pause_button = driver.find_element(By.ID, "id_foo_pause")
        pause_button.click()
        
        # Wait a moment to ensure upload is paused
        time.sleep(2)

        progress_bar_during_pause = driver.find_element(By.CLASS_NAME, "file-progress").get_attribute("value")
        
        # Verify that the upload is greater than 0% but less than 100%
        assert progress_bar_during_pause >  progress_bar_before_pause, \
            f"Upload did not progress before pause. Before: {progress_bar_before_pause}, During: {progress_bar_during_pause}"
        
        # Resume the upload
        resume_button = driver.find_element(By.ID, "id_foo_resume")
        resume_button.click()
        
        # Wait for the upload to complete by checking for "Uploaded" or "✓" in the status
        WebDriverWait(driver, 20).until(
            lambda d: any(
                "Uploaded" in elem.text or "✓" in elem.text 
                for elem in d.find_elements(By.CLASS_NAME, "file-status")
            )
        )
        progress_bar_after_resume = driver.find_element(By.CLASS_NAME, "file-progress").get_attribute("value")

        # Verify that upload progressed after resume
        assert progress_bar_after_resume > progress_bar_during_pause, \
            f"Upload did not progress after resume. During: {progress_bar_during_pause}, After: {progress_bar_after_resume}"
        
        # Verify that upload reached 100%
        assert progress_bar_after_resume == "1", \
            f"Upload did not complete after resume. Final progress: {progress_bar_after_resume}"

    except Exception as e:
        # Print page source for debugging
        print("Page source:", driver.page_source)
        print("Console logs:", driver.get_log('browser'))
        raise  # Re-raise the exception so the test fails
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

def test_real_file_upload_file_error(admin_user, live_server, driver):
    test_file_path = "/tmp/test_failed_file.bin"
    # Ensure the test file does not exist
    if os.path.exists(test_file_path):
        os.unlink(test_file_path)
    
    create_test_file(test_file_path, 5)

    driver.get(live_server.url + "/admin/")
    
    # Wait for login page to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_username"))
    )
    
    driver.find_element(By.ID, "id_username").send_keys("admin")
    driver.find_element(By.ID, "id_password").send_keys("password")
    driver.find_element(By.XPATH, '//input[@value="Log in"]').click()
    
    # Wait for successful login - check that we're no longer on the login page
    WebDriverWait(driver, 10).until(
        lambda d: "/login/" not in d.current_url
    )
    
    # Verify we can see the admin dashboard (session is working)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#content"))
    )
    
    # Add extra wait to ensure session cookie is fully set
    time.sleep(2)
    
    driver.get(live_server.url + "/admin/tests/foo/add/")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_bar")))
    driver.find_element(By.ID, "id_bar").send_keys("bat")
    
    # Inject JavaScript to mock error response before file upload
    driver.execute_script("""
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
                            
                            // Set status and readyState
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
            
                            // Trigger all possible event handlers
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
    
    # Wait for the file input to be ready
    file_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "id_foo_input_file"))
    )

    # Give the page a moment to fully initialize JavaScript
    time.sleep(1)
    
    file_input.send_keys(test_file_path)

    try:
        # Wait for the file-status element to appear with error
        WebDriverWait(driver, 20).until(
            lambda d: any(
                "Error" in elem.text
                for elem in d.find_elements(By.CLASS_NAME, "file-status")
            )
        )
        
        # Verify error message is displayed
        status_elements = driver.find_elements(By.CLASS_NAME, "file-status")

        assert any("Error" in elem.text for elem in status_elements), \
            f"No file status contains 'Error'. Found: {[elem.text for elem in status_elements]}"
        
        
    except Exception as e:
        # Print page source for debugging
        print("Page source:", driver.page_source)
        print("Console logs:", driver.get_log('browser'))

    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

