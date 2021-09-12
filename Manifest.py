import threading
import logging


class Manifest:
    def __init__(self):
        self.manifest = dict()
        self._lock = threading.Lock()
        logging.basicConfig(level=logging.DEBUG)

    def getManifest(self):
        with self._lock:
            return self.manifest

    def addDir(self, key, value=list()):
        logging.basicConfig(level=logging.DEBUG)
        with self._lock:
            if key not in self.manifest.keys():
                logging.debug(
                    "Manifest -- adding dir:{} to in manifest with files {}".format(
                        key, value
                    )
                )
                self.manifest[key] = value

    def addFileToDir(self, dirname, filename):
        with self._lock:
            logging.debug(
                "Manifest -- adding dir:{} and file:{} to manifest".format(
                    dirname, filename
                )
            )
            if dirname not in self.manifest.keys():  # check the directory exists
                new_files = list()
                new_files.append(filename)
                logging.debug(
                    "Manifest -- the value of dir:{} will be {} in manifest".format(
                        dirname, new_files
                    )
                )
                self.manifest[
                    dirname
                ] = new_files  # if not then make the directory and add the file using self.addDir()
            else:  # if the directory does exist
                files_list = self.manifest.get(dirname)  # retrieve the value
                logging.debug(
                    "Manifest -- the before value of dir:{} will is {} in manifest".format(
                        dirname, files_list
                    )
                )
                files_list.append(filename)  # add the filename to the list
                self.manifest[dirname] = files_list  # update the value
                logging.debug(
                    "Manifest -- Our new manifest is {}".format(self.manifest)
                )
