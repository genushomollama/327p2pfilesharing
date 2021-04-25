import logging
import threading
import re
import os
import socket
import platform

from Manifest import Manifest
from Node import Node
from ServerThread import ServerThread
from ClientThread import ClientThread

'''
Constants, port and address settings.
'''
# TODO pass debug status to the other threads so that debug statements aren't printed
MAIN_LOGGING_LEVEL = logging.INFO
CLIENT_LOGGING_LEVEL = logging.INFO
SERVER_LOGGING_LEVEL = logging.INFO
logging.basicConfig(level=MAIN_LOGGING_LEVEL)

SHARED_FOLDER = "Shared"
MANIFEST = Manifest()
MY_SHARED_FOLDER = socket.gethostname()
if platform.system() == 'Darwin':
    addr_data = os.popen('ipconfig getifaddr en0') # Assumption: the mac is using the default interface
    MY_SHARED_FOLDER = addr_data.read()
    logging.info("Instead of hostname we will be identifiable by reachable network addresss {}".format(MY_SHARED_FOLDER))
    logging.info("This is because on some Apple computers Bonjour is broken and cannot respond to the network hostname.")

# TODO lets record our ip address here as well
MAX_READ_SIZE = 2048 # this is the most bytes we will read from the network buffer at any given time, sending more could break the program. FIXME update this
CONTROL_PORT = 8091 # server will bind, listen, and accept incoming connections on this port
TIMEOUT_SEC = 5 # this is how many seconds our sockets will wait for a connection
currentNode = Node() # contains the addressing info for this Node in the linked-list
live_hosts = [] # node with nodeID of zero (the first node) will have none
contactPeer = None # the live_host that we will select to contact


'''
This function makes a call to arp for the arp table, it then makes a regex search for ip addresses, it returns
a list of ip addresses resident in the arp table.
'''
def extractAddress():
    hosts = list()
    with os.popen('arp -a') as f:
        data = f.read()
        data = re.findall('[0-9.]+', data)
        for item in data:
            octets = item.split(".")
            if len(octets) == 4:
                hosts.append(item)
    return hosts

'''
This method recursively populates the Manifest object in Main.
To invoke, provide the initialized manifest object and the filepath to the 'shared' folder.
'''
def populateManifest(manifest, wd):
    starting_dir = os.getcwd()
    logging.debug("starting in", starting_dir)
    os.chdir(wd)
    logging.debug("moved to", os.getcwd())
    resident_files = list()
    for item in os.listdir():
        if os.path.isdir(item):
            populateManifest(manifest, item)
        else:
            resident_files.append(item)
    dir_name = 'Shared' + os.getcwd().split('Shared')[1] # FIXME get path to current directory, cut off everything before SHARED
    manifest.addDir(dir_name, resident_files) # FIXME get the full path to the dir for the key, starts at 'Shared/...'
    os.chdir(starting_dir)


'''
This function accepts a list of ip addresses (as strings) and port number and then scans
the list of hosts for any running this program. Once one has been found, it will redirect
us to the host on the p2p network  responsible for adding new nodes to the network.
'''
def send_join_request(possiblePeer, CONTROL_PORT):
    logging.info("SEND_JOIN_REQUEST has been called on {}:{}".format(possiblePeer, CONTROL_PORT))
    next_ip = None
    last_ip = None
    id = None
    status = None
    complete = False
    index = 0
    while not complete:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_scanner:
            port_scanner.settimeout(TIMEOUT_SEC)
            try:
                complete = True
                port_scanner.connect((possiblePeer, CONTROL_PORT))
                port_scanner.send("JOIN".encode('ascii'))
                '''
                Two possible replies:
                "SUCCESS <assigned_id> <last_ip>" where las_ip will return the address of next newest host."
                or
                "REDIRECT <redirect_ip> -1 -1" where redirect will be sent the next join request."
                '''
                reply = port_scanner.recv(MAX_READ_SIZE)  # wait for reply
                response = reply.decode().split()
                status = response[0]
                if status == "SUCCESS":
                    id = response[1]
                    next_ip = possiblePeer
                    last_ip = response[2]
                elif status == "REDIRECT":
                    possiblePeer = response[1]
                    complete = False # make request to host we have been directed to
                else:
                    complete = True # FIXME why is this here?
                    raise Exception() # TODO learn how to do this right
                logging.debug(reply.decode()) # TODO eviscerate line, for debug
            except socket.timeout:
                logging.info("socket.timeout occurred, could not connect to {}".format(possiblePeer))
            except TimeoutError:
                logging.info("TimeoutError occurred, could not connect to {}".format(possiblePeer))
            except OSError:
                logging.info("OSError occurred, could not connect to {}".format(possiblePeer))
            except ConnectionRefusedError:
                logging.info("ConnectionRefusedError occurred, could not connect to {}".format(possiblePeer))
            finally:
                port_scanner.close()
    return (id, next_ip, last_ip) # initialization data for our node


'''
Start script, check that the Shared folder is in the filesystem.
Also check that the shared folder for this host is in the Shared folder.
If either is not there, then it will generate them.
'''
project_dir = os.listdir()
if SHARED_FOLDER not in project_dir: # if the folder that will house the unified set of documents does not exist, then make it
    os.mkdir(SHARED_FOLDER)
hosts_dir = os.listdir(SHARED_FOLDER)
if MY_SHARED_FOLDER not in hosts_dir: # if the folder that will house the documents we add to file set does not exist then make it
    shared_dir_location = SHARED_FOLDER + "/" + MY_SHARED_FOLDER
    os.mkdir(shared_dir_location)
populateManifest(MANIFEST, SHARED_FOLDER) # populate the MANIFEST object with the current set of files in the [outer] SHARED directory
present = MANIFEST.getManifest() # FIXME do we need this or is it for debug purposes

logging.debug("The current contents of our manifest {}".format(present)) # FIXME remove

'''
Scan the network for actively serving peers.
If any are found, try to join that overlay network.
If none are found, then start a new overlay network.
The architecture of this network is that of a simple doubly linked-list organized into a ring.
'''
live_hosts = extractAddress() # check ARP table for other hosts on the LAN
logging.info("Addresses we will attempt to connect to: {}".format(live_hosts))
if len(live_hosts) == 0: # start fresh network
    currentNode.setNodeID(0)
else: # attempt to join an existing network
    currentHost = 0 # contact lowest addressed host first
    searching = True
    while searching:
        contactPeer = live_hosts[currentHost]
        neighbor_data = send_join_request(contactPeer, CONTROL_PORT) # send a join request to the peer
        if neighbor_data[0] is not None: # this indicates a SUCCESS response was recieved
            currentNode.setNodeID(neighbor_data[0]) # populate data in Node object
            currentNode.setNext(neighbor_data[1])
            currentNode.setLast(neighbor_data[2])
            searching = False # TODO end update sections
        else:
            if currentHost >= len(live_hosts)-1: # no responses recieved, start a new overlay network
                currentNode.setNodeID(0)
                searching = False
            else:
                currentHost += 1 # check the next host in the ARP table # FIXme end uncomment this block after debugging

'''
Start the Kademlia DHT. This will probably requires a new thread.
'''
# TODO Kademlia DHT

'''
Start the server thread.
This will handle are incoming communications with clients (peers).
'''
serverThread = ServerThread(currentNode, CONTROL_PORT, MAX_READ_SIZE, MANIFEST) # declare server thread
serverThread.start() # start the server thread

'''
Start the client thread.
This will handle all communications initiated by this peer.
'''
clientThread = ClientThread(currentNode, CONTROL_PORT, MAX_READ_SIZE, MANIFEST) # declare client thread
clientThread.start() # start the client thread

'''
Wait for user to signal to shutdown the program.
Maybe set up a system to log messages to the cli.
If we do log messages then we should wait for the user to perform a keyboard interrupt, we can handle the
cleanup in the 'except KeyboardInterrupt' block.
'''
terminate = False
while not terminate:
    user_in = input("Enter 'exit' to terminate the program.\n>>").strip()
    if user_in == 'exit':
        terminate = True

'''
Make calls that signal the threads to perform cleanup operations and terminate the program.
'''
clientThread.cleanup()
serverThread.cleanup()
clientThread.join()
serverThread.join()

print("Goodbye.")
