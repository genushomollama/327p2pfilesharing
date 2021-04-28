import threading
import socket
import os
import os.path
import logging

from Node import Node


class ServerThread(threading.Thread):

    def __init__(self, current_node, server_port, data_trans_size, manifest, name='ServerThread'):
        self.node = current_node
        self.port = server_port
        self.MAX_DATA_TRANS = data_trans_size
        self.current_manifest = manifest  # will be set after request_manifest() is performed
        if self.node.getNodeID() == 0:
            self.network_size = 1
        else:
            self.network_size = -1
        self._stopevent = threading.Event()
        self.SOCKET_TIMEOUT = 2
        threading.Thread.__init__(self, name=name)

    ''' 
    Signal thread to finish tasks and finish execution.
    After calling this method a call to join can be made. FIXME did I get this wrong, should this be in join?
    '''
    def cleanup(self):
        self._stopevent.set()  # event will signal thread to finish it's task and exit cleanly

    '''
    Tell the previous node that the new node will be it's new 'next' neighbor.
    Returns true if the previous node acknowledges change.
    '''
    def updatePrevious(self, neighbor, new_neighbor):
        if neighbor is not None:
            success = False
            message = "UPDATE NEXT {}".format(new_neighbor)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as updater:  # open a socket for IPv4 TCP traffic
                updater.connect((neighbor, 8091))
                updater.send(message.encode('ascii'))
                reply = updater.recv(self.MAX_DATA_TRANS).decode().strip()
                if reply is "SUCCESS":
                    success = True
            return success
        else:
            return True

    '''
    Informs the next node (whose id is either greater than our own or zero) in the ring
    that a node has left and so id's should be decremented.
    Returns true if target system acknowledges the request.
    '''
    def forwardDecrement(self):
        success = False
        message = "DECREMENT"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as decrementer:  # open a socket for IPv4 TCP traffic
            decrementer.connect((self.node.getNext(), 8091))
            decrementer.send(message.encode('ascii'))
            reply = decrementer.recv(self.MAX_DATA_TRANS).decode().strip()
            if reply is "SUCCESS":
                success = True
        return success

    '''
    This function handles decrement requests. 
    Returns True if operation is success.
    '''
    def handleDecrement(self):
        success = True
        if self.node.getNodeID() == 0:
            self.network_size -= 1
        else:
            self.node.setNodeID(self.node.getNodeID() - 1)
            success = self.forwardDecrement()
        return success

    '''
    Sends a structured list of contents of shared filesystem to the requester in plaintext form.
    If there is already such a list in memory, send that, if not,
    generate a new list.
    Format will be as follows:
    DirNam1 residentfile1 residentfile2 residentfile3\n
    DirNam2 residentfile1 residentfile2 residentfile3\n
    '''
    def send_manifest(self, recipient_conn):
        manifest = self.current_manifest.getManifest() # retrieve manifest
        message = "" # message we will send to requester
        for dir in manifest.keys(): # iterate through contents, put then into string form
            line = dir
            dir_files = manifest[dir]
            line = line + " " + " ".join(dir_files) + "\n"
            message = message + line
        # open connection other host and send the manifest
        # open a socket for IPv4 TCP traffic
        manifest_size = len(message) # size of manifest in bytes
        # TODO if manifest to large then send in chunks
        if manifest_size < self.MAX_DATA_TRANS: # if the manifest is not to large then send it
            recipient_conn.send(message.encode('ascii'))
            recipient_conn.send("END".encode('ascii'))
        print("We have successfully sent the manifest")


    '''
    Sends a file to a requester.
    TODO raise and handle exceptions
    '''
    def serve_file(self, conn, filepath):
        print("Serving file {}".format(filepath))
        if os.path.exists(filepath):  # verify file exists
            file_size = os.path.getsize(filepath)  # get the size of file
            file_out = open(filepath, 'rb')  # open file for reading bytes
            header = "SUCCESS {}".format(file_size)  # send 'header' reply to client
            conn.send(header.encode('ascii'))
            sending_block = file_out.read(self.MAX_DATA_TRANS)
            sent_bytes = 0
            while sent_bytes < file_size:  # while still reading
                sent_bytes += conn.send(sending_block)  # send block
                sending_block = file_out.read(self.MAX_DATA_TRANS)  # read next block
            file_out.close()  # close file
        print("Finished serving file {}".format(filepath))

    '''
    Handles all incoming connections from other nodes.
    Depending on the request, server() invokes a number of other functions to fulfill it.
    '''
    def server(self, conn, client_ip, network_size=None):
        print("Entering the server function in ServerThread")
        data = conn.recv(2048)  # expected max ~ 1500 bytes
        print("We received the message {}".format(data.decode()))
        if data:
            print("Entering the decision in ServerThread")
            reply = None  # response message to client FIXME maybe should be None
            msg = data.decode()  # put message into string form

            if "JOIN" in msg:
                logging.debug("We received a JOIN request from {}".format(client_ip))
                print("Entering the join branch")
                if self.node.getNodeID() == 0:
                    logging.debug("We are node 0, we are serving the request")
                    self.updatePrevious(self.node.getLast(), client_ip)

                    reply = "SUCCESS {} {}".format(self.network_size, self.node.getLast())
                    self.network_size += 1 # increment so that next assignable node id is ready
                    print("Sending this reply to client:", reply)
                    self.node.setLast(client_ip)
                    logging.debug("Our last node is now {}".format(client_ip))
                    if self.node.getNext() is None:
                        self.node.setNext(client_ip)
                        logging.debug("Our next node is now {}".format(client_ip))
                    self.network_size += 1
                    print("We successfully allowed the new node to join our overlay network")
                else:
                    logging.debug("We are not node 0, we aren't serving the request")
                    reply = "REDIRECT {} -1 -1".format(self.node.getNext())  # redirect supplicant to the next node in the list
                conn.send(reply.encode('ascii'))
            elif msg.split()[0] == "UPDATE": # the topology has changed, accept new neighbors
                # TODO check valid message length
                if msg.split()[1] == "NEXT":
                    self.node.setNext(msg.split()[2])
                elif msg.split()[1] == "LAST":
                    self.node.setLast(msg.split()[2])
                elif msg.split()[1] == "VOID":
                    self.node.setLast(None)
                    self.node.setNext(None)
                else:
                    print("ERROR WE HAVE AN ERROR UPDATING OUR NODE INFORMATION", msg)  # TODO log error here
            elif msg.split()[0] == "DECREMENT":
                self.handleDecrement() # decrements id (unless 0), tells the NEXT node in chain to DECREMENT
            elif "MANIFEST" in msg:
                self.send_manifest(conn)
            elif "FILE" in msg:
                # TODO check valid message length
                print("calling serve file")
                self.serve_file(conn, msg.split()[1])
                print("we have served the file")
            else:
                print("THE REQUEST RECEIVED IS UNKNOWN:", msg)
                # TODO implement error handling
        print("finished serving client, continuing to listen for more connections :)")

    '''
    Opens a listening socket and dispatches other threads,
    running the server() function, to handle those connections.
    Stops accepting new connections when cleanup() is called.
    Afterwards join() can be called to terminate the thread.s
    '''
    def run(self):
        # bind, listen, while connection active accept
        logging.basicConfig(level=logging.INFO)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_listen:  # open a socket for IPv4 TCP traffic
            server_listen.settimeout(self.SOCKET_TIMEOUT)
            server_listen.bind(("", 8091))  # bind the socket to the host name and server port
            server_listen.listen()  # start listening for incoming connections
            while not self._stopevent.isSet():
                try:
                    conn, addr = server_listen.accept()  # block while waiting for new connections, these will be represented by the conn object
                    # start new thread to communicate with the client
                    client_connection = threading.Thread(target=self.server, args=(conn, addr[0], self.network_size))
                    client_connection.start()
                except socket.timeout:
                    pass # loop back and continue listening
                # TODO maybe handle OSERROR https://stackoverflow.com/questions/16734534/close-listening-socket-in-python-thread
