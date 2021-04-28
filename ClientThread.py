import math
import threading
import socket
import os
import time
import logging


class ClientThread(threading.Thread):

    def __init__(self, current_node, server_port, data_trans_size, manifest, name='ClientThread'):
        self.node = current_node
        self.port = server_port
        self.MAX_DATA_TRANS = data_trans_size
        self.current_manifest = manifest  # will be set after request_manifest() is performed
        self.sleep_time = 5  # seconds of sleep time
        self._stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)

    '''
    Signal client to finish it's tasks in preparation for exit.
    '''
    def cleanup(self):
        self._stopevent.set()  # event will signal thread to finish it's task and exit cleanly

    '''
    If a given filepath does not exist then recursively generate it.
    Preferably check beforehand that the directory exists before calling this function.
    '''
    def makeDirs(self, dir_path):
        logging.debug("Entering makeDirs")
        dirs = dir_path.split('/')
        current_path = ""
        if len(dirs) > 0:
            current_path = dirs.pop(0) # should be 'Shared', will already exist
            # FIXME if it doesn't exist then there is a problem, log it
        while len(dirs) > 0:
            current_dir = dirs.pop(0)
            current_path = current_path + "/" + current_dir
            current_dir_exists = os.path.exists(current_path)
            if not current_dir_exists:
                os.mkdir(current_path)
        logging.debug("Leaving makeDirs")

    '''
    Accept another node's manifest as plaintext, parse it into a new dict() structure.
    Return this as a dict() to caller.
    '''
    def process_manifest(self, data):
        output = dict()
        lines = data.split("\n")
        for line in lines:
            if len(line) > 0:
                items = line.split()
                if len(items) > 0:
                    current_key = items.pop(0)
                    current_values = items
                    output[current_key] = current_values
        return output

    '''
    Request manifest from a neighbor node. 
    Sent the plaintext manifest to self.process_manifest() for processing into a dictionary.
    Returns a dictionary that will be used to identify outstanding files, these will be downloaded
    and then added to our manifest.
    '''
    def request_manifest(self):
        logging.debug('ClientThread: entering request_manifest')
        logging.debug('ClientThread: request_manifest from next node {}'.format(self.node.getNext()))
        manifest = None  # will be a dict() if request is successful
        reply = ""
        if self.node.getLast() is not None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_conn:  # open a socket for IPv4 TCP traffic
                server_conn.settimeout(5)
                try:
                    server_conn.connect((self.node.getLast(), self.port))  # connect to the node pointed to by node.last
                    request = "MANIFEST VOID VOID" # expected request for a Manifest
                    server_conn.send(request.encode('ascii')) # send request
                    receiving_data = True
                    while receiving_data:
                        data = server_conn.recv(self.MAX_DATA_TRANS).decode() # get next chunk of manifest
                        if "END" not in data:
                            reply = reply + data
                        else:
                            receiving_data = False
                except socket.timeout:
                    logging.error("THE LAST NODE {} COULD NOT BE REACHED".format(self.node.getLast()))
                except socket.gaierror:
                    logging.error("THE ADDRESS OF LAST NODE {} WAS NOT VALID".format(self.node.getLast()))
                except ConnectionRefusedError:
                    logging.error("ConnectionRefusedError: Could not connect to the last node {}".format(self.node.getLast()))
            manifest = self.process_manifest(reply)
        logging.debug('ClientThread: leaving request_manifest we got this manifest {}'.format(manifest))
        return manifest

    '''
    Check this against our current manifest data.
    All files that we don't have will be added to a list containing tuples of (key, value) pairs from the dictionary.
    This list will be returned to the caller.
    '''
    def checkManifest(self, recv_manifest):
        logging.debug("Entering checkManifest() this is what we got {}".format(recv_manifest))
        files = list()
        manifest = self.current_manifest.getManifest()
        # iterate through keys
        for directory in recv_manifest.keys():
            files_in_dir = list()
            dir_exists = os.path.isdir(directory)# does directory exist
            dir_in_manifest = False # is the directory in the manifest already?
            if directory in manifest.keys():
                dir_in_manifest = True
            if not dir_exists: # NO
                # time to make records, make one for every item in dirs list,
                # if none only make a a record for that directory (dirname, None)
                files.append((directory, None))
            elif dir_in_manifest: # YES
                files_in_dir = manifest[directory] # get contents of directory in our manifest
            else:
                files_in_dir = list()
            for item in recv_manifest[directory]: # iterate through the items in recv_manifest[dir]
                if item not in files_in_dir:
                    files.append((directory, item)) # if any are missing, make a record for each
        logging.debug("Leaving checkManifest, this is what we got {}".format(files))
        return files # list of tuples [(dir1, file1), (dir3, file2), ...]

    '''
    Download all outstanding files from the neighbor's manifest.
    # TODO implement a ThreadPoolExecutor to issue requests & download files.
    Returns a list of file paths (to successfully downloaded files) to parse and record in the manifest.
    '''
    def download_files(self, files):
        logging.debug("Entering download_files(), we will attempt to download the following files {}".format(files))
        downloaded_files = list()  # records of downloaded files will be returned, list of file paths
        for item in files: # iterate through
            directory = item[0] # location of target directory
            filename = item[1] # filename

            if filename is not None:
                intermediate_dirs = directory.split("/")
                if len(intermediate_dirs) > 1: # if less than one than the only directory is 'Shared', this should not occur
                    hostname = intermediate_dirs[1]
                    # connect to host and download the file
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as neighbor_conn:
                        logging.debug("We have a opened a connection to the other host to get {}".format(filename))
                        neighbor_conn.connect((hostname, self.port))
                        file_location = directory + "/" + filename
                        request = "FILE {}".format(file_location)
                        neighbor_conn.send(request.encode('ascii'))  # request file from host
                        reply = neighbor_conn.recv(self.MAX_DATA_TRANS).decode().split()

                        if len(reply) == 2:
                            if reply[0] == "SUCCESS":
                                file_size = int(reply[1])
                                file_in = open(file_location, "wb")  # download location to filepath
                                num_recv_calls = 0 # number of calls to recv necessary to download file
                                recv_calls_made = 0 # number of calls to recv that we have made
                                if file_size < self.MAX_DATA_TRANS:
                                    num_recv_calls = 1
                                else:
                                    num_recv_calls = math.ceil(file_size/self.MAX_DATA_TRANS)
                                while recv_calls_made < num_recv_calls:
                                    data_in = neighbor_conn.recv(self.MAX_DATA_TRANS)  # check buffer for more data
                                    recv_calls_made += 1
                                    file_in.write(data_in)  # write the data to the file
                                logging.debug("We have finished downloading the file {}".format(filename))
                                file_in.close()
                                downloaded_files.append(item)
                            else:
                                logging.error("The serving peer can not serve the file {}/{}".format(directory, filename))
                        else:
                            logging.error("The request for the file {}/{} was met with an expected response".format(directory, filename))
            else:
                if not os.path.exists(directory):
                    self.makeDirs(directory)
                    downloaded_files.append(item)
        logging.debug("Leaving download_files() with the following files {}".format(downloaded_files))
        return downloaded_files

    '''
    Update this host's version of the manifest with downloaded files.
    We will receive a list of [(filepath, filename), ...] we will add these records
    to our manifest.
    '''
    def update_manifest(self, downloaded_files):
        logging.debug("Entering update_manifest()\nAdding the following files to manifest {}".format(downloaded_files))
        for item in downloaded_files:
            if item[1] is None:
                self.current_manifest.addDir(item[0], list())
            else:
                logging.debug("Adding {}/{} to manifest".format(item[0], item[1]))
                self.current_manifest.addFileToDir(item[0], item[1])
        logging.debug('ClientThread: Leaving update_manifest() with the updated manifest {}'.format(self.current_manifest.getManifest()))

    '''
    Send messages informing neighbor nodes that we are leaving the overlay.
    Tell neighbor nodes what nodes to connect to maintain link-list ring structure.
    Returns True if the neighbor/s acknowledge exit.
    # TODO handle any network problems that could arise
    '''
    def sendLeaveRequest(self, last_addr, next_addr=None):
        logging.debug("Entering sendLeaveRequest")
        success = False
        messages = []
        if next_addr is not None:
            messages.append("UPDATE LAST {}".format(last_addr))
            messages.append("UPDATE NEXT {}".format(next_addr))
            addresses = [last_addr, next_addr]
        else:
            messages.append("UPDATE VOID VOID")
            addresses = [last_addr]

        for i in range(len(messages)):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as neighbor_conn:
                try:
                    logging.debug("Sending leave request to {}".format(addresses[i]))
                    neighbor_conn.connect((addresses[i], self.port))
                    neighbor_conn.send(messages[i].encode('ascii'))
                    # reply = neighbor_conn.recv(self.MAX_DATA_TRANS).decode() # FIXME handle fail state
                    # if reply is "SUCCESS":
                    #     success = True
                    # elif reply is "FAILURE":
                    #     success = False
                except socket.gaierror:
                    logging.error("socket.gaierror occurred sending leave request to {}".format(addresses[i]))
                except socket.timeout:
                    logging.error("socket.timeout occurred sending leave request to {}".format(addresses[i]))
                except ConnectionRefusedError:
                    logging.error("ConnectionRefusedError occurred sending leave request to {}".format(addresses[i]))
                except OSError:
                    logging.error("OSError occurred sending leave request to {}".format(addresses[i]))
        logging.debug("Finished sending leave requests, we were".format(success))
        return success

    '''
    This function is called when this host leaves the overlay,
    it connects directly the neighboring nodes to maintain ring structure.
    '''
    def leaveOverlay(self):
        logging.debug("Entering leaveOverlay()")
        success = False
        last_addr = self.node.getLast()
        if last_addr is not None:
            next_addr = self.node.getNext()
            if last_addr == next_addr:
                logging.debug("Sending leave request to {}".format(last_addr))
                success = self.sendLeaveRequest(last_addr)
            else:
                logging.debug("Sending leave request to {} and {}".format(last_addr, next_addr))
                success = self.sendLeaveRequest(last_addr, next_addr)
        else:
            success = True
        logging.debug("Leaving leaveOverlay()")
        return success

    '''
    This function is called when the thread is run.
    It defines the series of events that will occur in a loop on the client thread.
    Calling cleanup() will signal the loop to finish it's work and stop.
    Afterwards join() can be called to terminate the thread.
    '''
    def run(self):
        logging.basicConfig(level=logging.INFO)
        while not self._stopevent.isSet():
            logging.debug('ClientThread: Starting loop')
            manifest = self.request_manifest()  # request the manifest
            if manifest is not None:
                logging.debug('ClientThread: Calling checkManifest')
                needed_files = self.checkManifest(manifest) # we will end up with a list of files
                # TODO we will make a call to the dht to locate a place to download each resource
                logging.debug('ClientThread: calling download_files')
                logging.debug("Sending needed files to the downloads", needed_files)
                # we will download each needed resource, and put into the proper directory (add directory if necessary)
                new_files = self.download_files(needed_files)
                logging.debug('ClientThread: calling update_manifest')
                self.update_manifest(new_files)  # update our manifest to reflect downloaded files
            time.sleep(self.sleep_time)# we might need to make a call to sleep or something here, maybe use a scheduler
        clean_exit = self.leaveOverlay()  # TODO something with clean_exit, if everything went well should be True
