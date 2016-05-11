import socket
import SocketServer
import threading
from struct import *
import binascii
from time import sleep
import requests


LISTENING_HOST = ""
LISTENING_PORTS = [6634, 6635, 6636]
TARGET_PORT = 6633
TARGET_HOSTS = ['127.0.0.1', '127.0.0.1', '127.0.0.1']
latency_measure = [-1, -1, -1]


class Forwarder(threading.Thread):
    def __init__(self, source):
        threading.Thread.__init__(self)
        self.source = source
        self.dest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dest.connect((TARGET_HOSTS[0], TARGET_PORT))

    def run(self):
        print "starting forwarder... "
        try:
            while True:
                data = self.dest.recv(4096)
                if len(data) == 0:
                    raise Exception("endpoint closed")
                #print "Received from dest: " + str(len(data))
                self.source.write_to_source(data)
        except Exception, e:
            print "EXCEPTION reading from forwarding socket"
            print e

        self.source.stop_forwarding()
        print "...ending forwarder."

    def write_to_dest(self, data):
        #print "Sending to dest: " + str(len(data))
        self.dest.send(data)

    def stop_forwarding(self):
        print "...closing forwarding socket"
        self.dest.close()



#class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
class ThreadedTCPRequestHandler(SocketServer.StreamRequestHandler):
    def handle(self):
        print "Starting to handle connection..."
        f = Forwarder(self)
        f.start()
        try:
            while True:
                data = self.request.recv(4096).strip()
                oftype = ParseRequest(data)
                #APPLY LB
                if len(data) == 0:
                    raise Exception("endpoint closed")
                f.write_to_dest(data)
        except Exception, e:
            print "EXCEPTION reading from main socket"
            print e

        #f.stop_forwarding()
        print "...finishing handling connection"


    def write_to_source(self, data):
        #print "Sending to source: " + str(len(data))
        self.request.send(data)

    def stop_forwarding(self):
        print "...closing main socket"
        self.request.close()


def ParseRequest(request):
    request = binascii.hexlify(request)
    ptype = int(request[0:2], 16)
    ofop = int(request[2:4], 16)
    if ptype == 4:
        print "Handled OF1.3 message "+GetOFTypeName(ofop)
        return ptype
    return -1


def MeasureLatency(instanceIP):
    for i in TARGET_HOSTS:
            print "Measuring controller latency for "+i
            try:
                r = requests.get('http://'+i+':8181/restconf/config/config:services/')
                latency_measure[TARGET_HOSTS.index(i)] = r.elapsed.total_seconds()
                print str(r.elapsed.total_seconds()) +' sec'
            except Exception, e:
                print repr(e)
                pass



class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    daemon_threads = True
    allow_reuse_address = True



if __name__ == "__main__":
    server_one = ThreadedTCPServer((LISTENING_HOST, LISTENING_PORTS[0]), ThreadedTCPRequestHandler)
    server_two = ThreadedTCPServer((LISTENING_HOST, LISTENING_PORTS[1]), ThreadedTCPRequestHandler)
    server_three = ThreadedTCPServer((LISTENING_HOST, LISTENING_PORTS[2]), ThreadedTCPRequestHandler)
    ip, port = server_one.server_address
    server_one_thread = threading.Thread(target=server_one.serve_forever)
    server_one_thread.daemon = True
    server_one_thread.start()
    print "Server loop running on port ", port
    ip, port = server_two.server_address
    server_two_thread = threading.Thread(target=server_two.serve_forever)
    server_two_thread.daemon = True
    server_two_thread.start()
    print "Server loop running on port ", port
    ip, port = server_three.server_address
    server_three_thread = threading.Thread(target=server_three.serve_forever)
    server_three_thread.daemon = True
    server_three_thread.start()
    print "Server loop running on port ", port

    MeasureLatency('localhost')

    try:
        while True:
            sleep(1)
    except:
        pass
    print "...servers stopping."
    server_one.shutdown()
    server_two.shutdown()
    server_three.shutdown()


def GetOFTypeName(ofop):
    return {
        0 : 'HELLO',
        1 : 'ERROR',
        2 : 'ECHO_REQ',
        3 : 'ECHO_RES',
        4 : 'EXPERIMENTER',
        5 : 'FEATURE_REQ',
        6 : 'FEATURE_RES',
        7 : 'GET_CONFIG_REQ',
        8 : 'GET_CONFIG_RES',
        9 : 'SET_CONFIG',
        10 : 'PACKET_IN',
        11 : 'FLOW_REMOVED',
        12 : 'PORT_STATUS',
        13 : 'PACKET_OUT',
        14 : 'FLOW_MOD',
        15 : 'GROUP_MOD',
        16 : 'PORT_MOD',
        17 : 'TABLE_MOD',
        18 : 'MULTIPART_REQ',
        19 : 'MULTIPART_RES',
        20 : 'BARRIER_REQ',
        21 : 'BARRIER_RES',
        22 : 'QUEUE_GET_CONFIG_REQ',
        23 : 'QUEUE_GET_CONFIG_RES',
        24 : 'ROLE_REQ',
        25 : 'ROLE_RES',
        26 : 'GET_ASYNC_REQ',
        27 : 'GET_ASYNC_RES',
        28 : 'SET_ASYNC',
        29 : 'METER_MOD',
    }.get(ofop, '')
