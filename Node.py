import threading

'''
Node will provide a structure to store the necessary information to communicate with neighbors of the doubly linked-list.
Additionally it keeps track of numeric ID given to this machine, which in turn dictates the responsibilities this peer is 
given in the network.
The machine with a nodeID of 0 will be responsible for admitting new peers to the network.
Node is protected by mutex locks and thus calls to it's functions will result in blocking calls.
Do not attempt to access the attributes directly, as this could result in unexpected behaviours.
Node will be implemented following the Singleton design pattern.
'''
class Node:
    def __init__(self):
        self.nodeID = -1
        self.next = None
        self.last = None
        self.nodeID = -1 # Peer with NodeID 0 will keep track of size of network, else it will be -1
        self._lock = threading.Lock()

    def getNodeID(self):
        with self._lock:
            return self.nodeID

    def setNodeID(self, newID):
        with self._lock:
            self.nodeID = newID

    def getNext(self):
        with self._lock:
            return self.next

    def setNext(self, newNext):
        with self._lock:
            self.next = newNext

    def getLast(self):
        with self._lock:
            return self.last

    def setLast(self, newLast):
        with self._lock:
            self.last = newLast

    def printMessage(self): # TODO delete this for debug purposes.
        print("I am node %d" % self.nodeID)
