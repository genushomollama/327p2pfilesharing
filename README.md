 
# Peer-to-Peer LAN Filesharer
## What is this? 
This program is a peer-to-peer file sharing program for simple SOHO LANs. 

It is written in python, and uses only low-level socket calls in all connections.

## How to use
1. clone project
2. optional: 
	- Make a directory within '/Shared', the name should be the reachable ip address of of the host (as in an ipv4 address either obtained from a DHCP lease or from the host itself, i.e. APIPA), a resolvable hostname or alias can also serve this purpose. 
		- For example, if the address of the local host is 192.168.0.112 then the operator could issue the command 
		`mkdir Shared/192.168.0.112` 
	- The operator can put any files they wish to share with other peers on the network in this directory. 
	
	Note: if you choose to skip this step the program will make the appropriate directory at runtime. 
3. Run the program with the following command `python3 Main.py` 
4. The program will prompt you to enter the command exit to terminate the program. In the current iteration of this project terminating the program without entering the exit command may very well break the overlay network, in which case the program would have to simply be restarted on some of the hosts belonging to the network (otherwise, no harm done).

## Next steps:
-   use the Kademlia DHT to perform optimization
-   include functionality for pushing file updates and file delete notifications to other peers
-   use a ThreadPoolExecutor to speed up the process of downloading many files simultaneously
-   display the progress of current downloads to the operator via animated progress bars

## Bugs and current issues
-   Calls to decode() fail when handling multimedia objects, damaging the contents of those received files, functionality must be added to handle encodings involving non utf-8 characters. This results in some distortion in .png images that have been downloaded.

<p align="center">  <img src="https://github.com/genushomollama/327p2pfilesharing/blob/main/multimedia_bug.png?raw=true">  </p>

## How it works
### Network Architecture

<p align="center">  <img src="https://raw.githubusercontent.com/genushomollama/327p2pfilesharing/main/overlay.png">  </p>

-   each host is a node in a doubly linked list 
	-  each node has a unique ID
	-  the node with an ID of 0 is responsible for admitting new nodes into the network

### Program Structure
Three or more threads of execution are taking place most of the time in this program. The most important are Main, ClientThread, and ServerThread.

<p align="center">  <img src="https://raw.githubusercontent.com/genushomollama/327p2pfilesharing/main/threads.png">  </p>

1. Main:
	- Searches ARP table for other peers on network, contacts each host until a peer is found, in the case no peers are found a new overlay network is started in which this host will have the id of 0
	- Launches ServerThread
	- Launches ClientThread
	- Waits for user to enter 'exit' at the command line
	- After the user has indicated the program should close, flags are set in both ClientThread and ServerThread that instruct them to finish the jobs they are currently doing, and then terminate gracefully.
	- Once ClientThread and ServerThread have terminated then Main terminates as well.
2. ServerThread:
	- When the start() method of ServerThread is invoked by the Main, ServerThread enters into a loop in the function run() wherein it initiates a socket to listen for and accept incoming connections from peers. When a connection is accepted it handed to a new thread which runs the method ServerThread.server() concurrently. 
	- The thread running ServerThread.server() handles requests from peers, it serves the following types of request from other peers:
		- a JOIN request from a node asking to join the overlay
		- an UPDATE request from a node asking us to update our references to the last/next nodes 
		- a DECREMENT request instructing our host to decrement our NodeID
		- a MANIFEST request asking our host to provide a listing of our current shared files
		- a FILE request asking our host to serve a given file
3. ClientThread:
	- When the start() method of ClientThread is invoked by the Main, ClientThread enters into a loop that does the following
		- a request is made to previous node in the overlay (in the circular doubly linked-list) for the listing of all files and directories in their '/Shared' directory, we call this the MANIFEST
		- for each file that the previous node has that this host does not, requests are made iteratively to other peers to download these files
		- each downloaded file is added to our MANIFEST, ServerThread this will the updated Manifest to the next peer in our overlay when they request it
		- the thread will sleep for some period of time 
		- if the flag to terminate has not been set then the loop will run again
	- Once Main has signaled the ClientThread to terminate it will send messages to it's neighbors informing them that it is leaving the overlay, those nodes will then update their pointer references to reflect that.
