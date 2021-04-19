import threading

class Manifest:
    def __init__(self):
        self.manifest = dict()
        self._lock = threading.Lock()

    def getManifest(self):
        with self._lock:
            return self.manifest

    def addDir(self, key, value=list()):
        with self._lock:
            if key not in self.manifest.keys():
                self.manifest[key] = value

    def addFileToDir(self, dirname, filename):
        with self._lock:
            if dirname not in self.manifest.keys(): # check the directory exists
                new_files = list().append(filename)
                self.manifest[dirname] = new_files # if not then make the directory and add the file using self.addDir()
            else: # if the directory does exist
                files_list = self.manifest.get(dirname) # retrieve the value
                files_list.append(filename) # add the filename to the list
                self.manifest[dirname] = files_list # update the value

