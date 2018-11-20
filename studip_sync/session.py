import os
import shutil
import requests
from studip_sync import parsers


class SessionError(Exception):
    pass


class LoginError(SessionError):
    pass


class DownloadError(SessionError):
    pass


class URL(object):
    @staticmethod
    def login_page():
        return "https://lms.ph-karlsruhe.de/studip/index.php?again=yes"

    @staticmethod
    def files_main():
        return "https://lms.ph-karlsruhe.de/studip/dispatch.php/course/files"

    @staticmethod
    def bulk_download(folder_id):
        return "https://lms.ph-karlsruhe.de/studip/dispatch.php/file/bulk/{}".format(folder_id)

    @staticmethod
    def studip_main():
        return "https://lms.ph-karlsruhe.de/studip/"

    @staticmethod
    def courses():
        return "https://lms.ph-karlsruhe.de/studip/dispatch.php/my_courses"


class Session(object):

    def __init__(self):
        super(Session, self).__init__()
        self.session = requests.Session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.__exit__()

    def login(self, username, password):
        with self.session.get(URL.login_page()) as response:
            if not response.ok:
                raise LoginError("Cannot access Stud.IP login page")
            sso_url = parsers.extract_sso_url(response.text)
        login_data = {
            "loginname": username,
            "password": password,
            "donotcache": 1,
            "_eventId_proceed": ""
        }
        login_data.update(parsers.extract_ph(response.text))
        with self.session.post(sso_url,data=login_data) as response:
            if not response.ok:
                raise LoginError("Cannot access SSO server")
        with self.session.get(URL.studip_main()) as response:
            if not response.ok:
                raise LoginError("Cannot access Stud.IP main page")
            
        
    def get_courses(self):
        with self.session.get(URL.courses()) as response:
            if not response.ok:
                raise SessionError("Failed to get courses")
            
            return parsers.extract_courses(response.text)

    def download(self, course_id, workdir, sync_only=None):
        params = {"cid": course_id}

        with self.session.get(URL.files_main(), params=params) as response:
            if not response.ok:
                raise DownloadError("Cannot access course files page")
            folder_id = parsers.extract_parent_folder_id(response.text)
            csrf_token = parsers.extract_csrf_token(response.text)

        download_url = URL.bulk_download(folder_id)
        data = {
            "security_token": csrf_token,
            # "parent_folder_id": folder_id,
            "ids[]": sync_only or folder_id,
            "download": 1
        }

        with self.session.post(download_url, params=params, data=data, stream=True) as response:
            if not response.ok:
                raise DownloadError("Cannot download course files")
            path = os.path.join(workdir, course_id)
            with open(path, "wb") as download_file:
                shutil.copyfileobj(response.raw, download_file)
                return path
