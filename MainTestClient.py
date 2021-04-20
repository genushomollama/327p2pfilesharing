import threading
import re
import os
import socket

from Manifest import Manifest
from Node import Node
# import Functions
from ServerThread import ServerThread
from ClientThread import ClientThread

'''
Constants, port and address settings.
'''
SHARED_FOLDER = "Shared"
MANIFEST = Manifest()
MY_SHARED_FOLDER = socket.gethostname()
# TODO lets record our ip address here as well
MAX_READ_SIZE = 2048 # this is the most bytes we will read from the network buffer at any given time, sending more could break the program. FIXME update this
CONTROL_PORT = 8091 # server will bind, listen, and accept incoming connections on this port
currentNode = Node() # contains the addressing info for this Node in the linked-list
live_hosts = [] # node with nodeID of zero (the first node) will have none
contactPeer = None # the live_host that we will select to contact


'''
Functions
'''

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
    print("starting in", starting_dir)
    os.chdir(wd)
    print("moved to", os.getcwd())
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
'''
# TODO rewrite this function it is terrible
def send_join_request(possiblePeer, CONTROL_PORT):
    print("SEND_JOIN_REQUEST has been called on {}:{}".format(possiblePeer, CONTROL_PORT))
    next_ip = None
    last_ip = None
    assigned_node_id = None
    status = None
    complete = False
    index = 0
    while not complete:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_scanner:
            port_scanner.settimeout(10)
            reply = ""
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
                response = reply.decode()
                print("Received this response from server:", response)
                # status = response[0]
                if "SUCCESS" in response:
                    overlay_data = response.split()
                    assigned_node_id = overlay_data[1]
                    next_ip = possiblePeer
                    if overlay_data[2] == "None":
                        last_ip = possiblePeer # in this case there is only one other host on the overlay
                    else:
                        last_ip = overlay_data[2] # in this case there is already more than one host in the overlay
                elif status == "REDIRECT":
                    possiblePeer = response[1]
                    complete = False # make request to host we have been directed to
                else:
                    complete = True # FIXME why is this here?
                    raise Exception() # TODO learn how to do this right
                print(reply.decode()) # TODO eviscerate line, for debug
                # print the reply TODO destroy line
            except OSError:
                print("OSerror")  # many
            except TimeoutError:
                print("Connection timed out")  # 0
            except socket.timeout:
                print("It was the socket.timeout thing that worked")  # 0
            except ConnectionRefusedError or OSError:  # formerly many, OSerror catches most everything
                print("Connection refused!")
            except socket.timeout:
                print("The socket timed out, no response was recieved")  # loop back and continue listening
            finally:
                port_scanner.close()
    return (assigned_node_id, next_ip, last_ip)

'''
Start the script.
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

print(present) # FIXME remove



'''
Scan the network for actively serving peers.
If any are found, try to join that overlay network.
If none are found, then start a new overlay network.
The architecture of this network is that of a simple doubly linked-list.
'''
# live_hosts = extractAddress() # check ARP table for other hosts on the LAN # FIXME start uncomment this block after debugging
# print("Addresses extracted: ", live_hosts) # FIXME for debug purposes
# if len(live_hosts) == 0: # start fresh network
#     currentNode.setNodeID(0)
# else: # attempt to join an existing network
#     currentHost = 0 # contact lowest addressed host first
#     searching = True
#     while searching:
#         contactPeer = live_hosts[currentHost]
#         neighbor_data = send_join_request(contactPeer, CONTROL_PORT) # send a join request to the peer
#         if neighbor_data[0] is not None: # this indicates a SUCCESS response was recieved
#             currentNode.setNodeID(neighbor_data[0]) # populate data in Node object
#             currentNode.setNext(neighbor_data[1])
#             currentNode.setLast(neighbor_data[2])
#             searching = False # TODO end update sections
#         else:
#             if currentHost >= len(live_hosts)-1: # no responses recieved, start a new overlay network
#                 currentNode.setNodeID(0)
#                 searching = False
#             else:
#                 currentHost += 1 # check the next host in the ARP table # FIXME end uncomment this block after debugging

# FIXME start remove section DEBUG
neighbor_data = send_join_request('192.168.0.233', CONTROL_PORT) # send a join request to the peer
print("The data recieved from send_join_request is {}".format(neighbor_data))
if neighbor_data[0] is not None: # this indicates a SUCCESS response was recieved
    currentNode.setNodeID(neighbor_data[0]) # populate data in Node object
    currentNode.setNext(neighbor_data[1])
    currentNode.setLast(neighbor_data[2])

if currentNode.getNext() is None:
    print("No peers were found, we have started our own overlay network")
else:
    print("We have joined an overlay network, out node info:", currentNode.getNodeID(), currentNode.getNext(), currentNode.getLast())
# FIXME end remove section DEBUG

'''
Start the Kademlia DHT. This will probably requires a new thread.
'''
# TODO Kademlia DHT

'''
Start the server thread.
This will handle are incoming communications with clients (peers).
'''
# serverThread = ServerThread(currentNode, CONTROL_PORT, MAX_READ_SIZE, MANIFEST) # declare server thread
# serverThread.start() # start the server thread

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
# serverThread.cleanup()
clientThread.join()
# serverThread.join()

print("Goodbye.")


