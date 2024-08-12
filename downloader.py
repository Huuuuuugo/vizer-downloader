import threading
import warnings
import time
import os

import requests


#TODO: make it handle unexpected status codes
class Download():
    def __init__(self, url: str, file_name: str):
        self.url = url
        self.file_name = file_name
        self.is_running = False

        self._interrupt_download = False

        # get ammount of bytes already written before beggining
        if os.path.exists(file_name):
            self.written_bytes = os.path.getsize(self.file_name)
        else:
            self.written_bytes = 0
        
        # set range to resume download if any byte has already been written
        if self.written_bytes:
            headers = {
                "Range": f"bytes={self.written_bytes}-"
            }
        else:
            headers = {}

        self.response = requests.get(url, headers=headers, stream=True)
        self.total_size = self.written_bytes + int(self.response.headers['Content-Length'])

    @property
    def progress(self):
        return self.written_bytes/(self.total_size/100)

    @progress.setter
    def progress(self, value):
        return self.written_bytes/(self.total_size/100)
    
    def start(self):
        def download():
            self.is_running = True
            with open(self.file_name, 'ab') as file:
                for chunk in self.response.iter_content(chunk_size=8192):
                    if chunk:
                        self.written_bytes += len(chunk)
                        file.write(chunk)

                    if self._interrupt_download:
                        self.written_bytes = os.path.getsize(self.file_name)
                        break
                    
            self.is_running = False
            self._interrupt_download = False
        
        if self.response.status_code not in (200, 206):
            message = f"Unexpected status code: {self.response.status_code}."
            raise requests.RequestException(message)

        if self.progress >= 100:
            message = "Can't start a download that's already finished."
            warnings.warn(message, RuntimeWarning)
            return
        
        if self.is_running:
            message = "Can't start a download that's already running."
            warnings.warn(message, RuntimeWarning)
            return
        
        threading.Thread(target=download, daemon=True).start()
    
    def stop(self):
        if not self.is_running:
            message = "Can't stop a download that's not running."
            warnings.warn(message, RuntimeWarning)
            return
        
        # set flag to interrupt the download thread and wait for it to properly stop
        self._interrupt_download = True
        while self.is_running:
            time.sleep(0.0001)
        
