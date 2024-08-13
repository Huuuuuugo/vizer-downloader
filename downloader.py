import threading
import warnings
import time
import os

import requests


#TODO: create context manager for properly closing files
class Download():
    """A class to manage the download of files, supporting resumable downloads and progress tracking.

    Attributes:
    -----------
    download_list : list
        A class-level list that tracks all active download instances.
    
    url : str
        The URL of the file to be downloaded.
    
    output_file : str
        The file path where the downloaded content will be saved.
    
    is_running : bool
        Indicates if the download is currently running.
    
    _interrupt_download : bool
        A private attribute used to interrupt the download thread.
    
    total_size : int
        The total size of the file to be downloaded in bytes.
    
    written_bytes : int
        The number of bytes already written to the output file.
    
    response : requests.Response
        The HTTP response object for the file download.
    """
        
    download_list = []

    def __init__(self, url: str, output_file: str):
        """Initializes a Download instance.

        Parameters:
        -----------
        url : str
            The URL of the file to be downloaded.
        
        output_file : str
            The file path where the downloaded content will be saved.
        
        Raises:
        -------
        TypeError:
            If the `url` attribute is not of type `str`.
        
        ValueError:
            If another Download object is already using the specified `output_file`.
        
        requests.RequestException:
            If the initial request to get the file size returns an unexpected status code.
        
        requests.RequestException:
            If the request to get the file returns an unexpected status code.
        
        Side Effects:
        -------------
        Appends the created Download object to the class-level download_list.
        """
        
        if not isinstance(url, str):
            Download.stop_all()
            message = f"Invalid type for 'url' attribute."
            raise TypeError(message)

        for download in Download.download_list:
            if download.output_file == output_file:
                Download.stop_all()
                message = f"Invalid value for 'output_file' attribute. There's already a Download object using the file at '{output_file}'"
                raise ValueError(message)
        
        self.url = url
        self.output_file = output_file
        self.is_running = False
        self._interrupt_download = False

        # make a request to get the total size of the file
        request_size = requests.get(url)
        if request_size.status_code not in (200, 206):
            Download.stop_all()
            message = f"Unexpected status code when requesting file size: {request_size.status_code}."
            raise requests.RequestException(message)
        
        self.total_size = int(request_size.headers['Content-Length'])
        request_size.close()

        # get ammount of bytes already written before beggining
        if os.path.exists(output_file):
            self.written_bytes = os.path.getsize(self.output_file)
        else:
            self.written_bytes = 0
        
        # set range to resume download if any byte has already been written
        if self.written_bytes:
            headers = {
                "Range": f"bytes={self.written_bytes}-"
            }

        else:
            headers = {}

        if self.written_bytes == self.total_size:
            self.response = request_size
        else:
            self.response = requests.get(url, headers=headers, stream=True)
        
        if self.response.status_code not in (200, 206):
            Download.stop_all()
            message = f"Unexpected status code: {self.response.status_code}."
            raise requests.RequestException(message)

        Download.download_list.append(self)

    @property
    def progress(self):
        """Calculate the download progress as a percentage.

        Returns:
        --------
        float
            The progress of the download as a percentage (0 to 100).
        """

        return self.written_bytes/(self.total_size/100)
    
    @classmethod
    def wait_downloads(cls, show_progress: bool = True):
        """Waits for all downloads to complete. Optionally shows progress in the terminal.

        Parameters:
        -----------
        show_progress : bool, optional
            If True, prints the progress of each download (default is True).
        
        Side Effects:
        -------------
        Updates the terminal output with the download progress.
        """

        while True:
            wait = False
            for download in cls.download_list:
                if show_progress:
                    print(f"{download.output_file}: {download.progress:.2f}")

                if download.progress >= 100:
                    continue

                elif download.is_running:
                    wait = True

            if show_progress:
                print("\033[A"* len(cls.download_list), end='\r')

            if not wait:
                break
            
            time.sleep(0.2)
        
        if show_progress:
            print("\033[B" * len(Download.download_list), end='')
    
    @classmethod
    def stop_all(cls):
        """Stops all currently running downloads.

        Side Effects:
        -------------
        Interrupts and stops all active download threads.
        """

        for download in cls.download_list:
            if download.is_running:
                download.stop()
    
    def start(self):
        """Starts the download process in a separate thread.
        
        Warns:
        ------
        RuntimeWarning:
            If the download is already completed or currently running.
        
        Side Effects:
        -------------
        Spawns a new thread to handle the download process.
        """

        def download():
            self.is_running = True
            with open(self.output_file, 'ab') as file:
                for chunk in self.response.iter_content(chunk_size=8192):
                    if chunk:
                        self.written_bytes += len(chunk)
                        file.write(chunk)

                    if self._interrupt_download:
                        self.written_bytes = os.path.getsize(self.output_file)
                        break
                    
            self.is_running = False
            self._interrupt_download = False

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
        """Stops the current download if it is running.

        Warns:
        ------
        RuntimeWarning:
            If the download is not currently running.
        
        Side Effects:
        -------------
        Interrupts the download thread and waits for it to stop.
        """

        if not self.is_running:
            message = "Can't stop a download that's not running."
            warnings.warn(message, RuntimeWarning)
            return
        
        # set flag to interrupt the download thread and wait for it to properly stop
        self._interrupt_download = True
        while self.is_running:
            time.sleep(0.0001)
        

if __name__ == "__main__":
    try:
        download1 = Download(r"https://github.com/gorhill/uBlock/releases/download/1.59.0/uBlock0_1.59.0.firefox.signed.xpi", "uBlock0_1.59.0.firefox.signed.xpi")
        download2 = Download(r"https://github.com/gorhill/uBlock/releases/download/1.59.0/uBlock0_1.59.0.firefox.signed.xpi", r"C:\Users\hugom\OneDrive\Área de Trabalho\adt\adt2\uBlock0_1.59.0.firefox.signed.xpi")

        download1.start()
        download2.start()

        Download.wait_downloads()
    
    except KeyboardInterrupt:
        Download.stop_all()