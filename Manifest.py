import threading
import logging


class Manifest:
    def __init__(self):
        self.manifest = dict()
        self.manifest["files"] = list()
        self.manifest["ctimes"] = dict()
        self.manifest["mtimes"] = dict()
        self._lock = threading.Lock()
        logging.basicConfig(level=logging.DEBUG)

    def getManifest(self):
        with self._lock:
            return self.manifest


    def addFile(self, filepath, ctime, mtime):
        with self._lock:
            logging.debug(
                "Manifest -- adding filepath:{} to manifest".format(
                    filepath
                )
            )
             # if the file is not already in the manifest then add it
            if filepath not in self.manifest["files"]:
                self.manifest["files"].append(filepath)
                self.manifest["ctimes"][filepath] = ctime
                self.manifest["mtimes"][filepath] = mtime


