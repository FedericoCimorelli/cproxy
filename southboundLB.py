########################
# requirements:
# sudo apt-get install mz
########################

import socket
import SocketServer
import threading
import binascii
from time import sleep
import time
from collections import defaultdict
import csv
#from termcolor import colored


#setup ovs switches according...
CSV_FILE_NAME = 'output.csv'
CSV_OUTPUT_FILE = open(CSV_FILE_NAME, 'wb')
CSV_OUTPUT_WRITER = csv.writer(CSV_OUTPUT_FILE)
LB_PORTS = [6634, 6635, 6636]
CONTROLLERS_PORT = 6633
CONTROLLERS_COUNT = 1
CONTROLLERS_IP = ['10.42.0.196', '10.42.0.188', '10.42.0.42']
MININET_IP = '10.42.0.96'
LATENCY_AVG_MEASURES_NUM = 20
LATENCY_MEASURES = defaultdict(list)
OF_TEST_FLOWMOD_TS = defaultdict(list)
OF_TEST_FLOWMOD_LATENCY = []
OF_REQ_FORWARDERS = []
FORWARDING_SCHEME = None #Set it in main method



class StaticForwarder():
    name = 'static'

    def __init__(self):
        pass

    def getControllerDestIndex(self, sourcePort):
        if sourcePort == LB_PORTS[0]:
            return 0
        if sourcePort == LB_PORTS[1]:
            return 1
        if sourcePort == LB_PORTS[2]:
            return 2



class RoundRobinForwarder():
    name = 'roundrobin'
    last_index = 0

    def __init__(self):
        pass

    def getControllerDestIndex(self, sourcePort):
        return (self.last_index+1)%CONTROLLERS_COUNT



class WardropForwarder():
    name = 'wardrop'
    probs = []

    def __init__(self):
        for i in range(CONTROLLERS_COUNT):
            self.probs.append(1/CONTROLLERS_COUNT)

    def update(self, controllerIp, controllerNewLatency):
        #TODO
        print 'INFO    Wardrop forwarder, updated probs: ' + str(self.probs)

    def getControllerDestIndex(self, sourcePort):
        return self.probs.index(min(self.probs))




def getStaticControllerIndexFromOFport(port):
    if port == LB_PORTS[0]:
        return 0
    if port == LB_PORTS[1]:
        return 1
    if port == LB_PORTS[2]:
        return 2





class OpenFlowRequestForwarder(threading.Thread):

    socket_to_odl = None
    serverListeningPort = 6633

    def __init__(self, client_address, serverListeningPort):
        threading.Thread.__init__(self)
        self.client_address = client_address
        self.serverListeningPort = serverListeningPort
        self.socket_to_odl = []
        targetControllerIndex = getStaticControllerIndexFromOFport(self.serverListeningPort)
        print 'INFO    Setting OpenFlowRequestHandler socket from ' \
              + str(client_address.client_address) + ' to ' + str(CONTROLLERS_IP[targetControllerIndex]) + ':' + str(CONTROLLERS_PORT)
        self.socket_to_odl = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket_to_odl.connect((CONTROLLERS_IP[targetControllerIndex], CONTROLLERS_PORT))
        except Exception, e:
            print e

    def run(self):
        try:
            while True:
                data = self.socket_to_odl.recv(65565)
                if len(data) != 0:
                    source = str(self.socket_to_odl.getpeername()[0]) + ":" + str(self.socket_to_odl.getpeername()[1])
                    ofop = ParseRequestForOFop(data, source)
                    if ofop == 14: #FLOW_MOD
                        address = ParseFlowModRequestForAddress(data)
                        if address != '':
                            #WHICH  CONTROLLER=?????
                            latency = ComputeOFopLatency(address, self.socket_to_odl.getpeername())
                            if FORWARDING_SCHEME.name == 'wardrop' and latency != -1:
                                FORWARDING_SCHEME.update(self.socket_to_odl.getpeername(), latency)
                    #if len(data) == 0:
                    #    raise Exception("endpoint closed")
                    self.client_address.write_to_source(data)
        except Exception, e:
            print "ERROR   Exception reading from forwarding socket"
            print e
            pass
        self.client_address.stop_forwarding()

    def write_to_dest(self, data, OFop=0):
        self.socket_to_odl.send(data)

    def stop_forwarding(self):
        self.socket_to_odl.close()




class OFSouthboundRequestHandler(SocketServer.StreamRequestHandler):

    def handle(self):
        print "INFO    Starting to handle connection..."
        OFReqForwarders = []
        if len(OFReqForwarders) == 0:
            for i in range(CONTROLLERS_COUNT):
                print 'INFO    Setting OpenFlowRequestHandler socket from ' \
                      + str(MININET_IP) + ' to ' + str(CONTROLLERS_IP[i]) + ':' + str(CONTROLLERS_PORT)
                OFReqForwarders.append(OpenFlowRequestForwarder(self, self.server.serverListeningPort))
                OFReqForwarders[i].start()
        try:
            while True:
                data = self.request.recv(65565)
                #if len(data) == 0:
                #    raise Exception("endpoint closed")
                if len(data) != 0:
                    ofop = ParseRequestForOFop(data, str(MININET_IP) + ':' + str(self.server.serverListeningPort))
                    if ofop == 10: #on PACKET_IN
                        address = ParsePacketInRequestForAddress(data)
                        if address != '':
                            OF_TEST_FLOWMOD_TS[address].append(time.time())
                        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        #!!!!!!!!!!!!!APPLY HERE THE LB NOW!!!!!!!!!!!!!!
                        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        targetControllerIndex = FORWARDING_SCHEME.getControllerDestIndex(self.server.serverListeningPort)
                        OFReqForwarders[targetControllerIndex].write_to_dest(data, ofop)
                    else:
                        targetControllerIndex = getStaticControllerIndexFromOFport(self.server.serverListeningPort)
                    OFReqForwarders[targetControllerIndex].write_to_dest(data, ofop)
        except Exception, e:
            print "ERROR   Exception reading from main socket"
            print e
        for i in range(CONTROLLERS_COUNT):
            OFReqForwarders[i].stop_forwarding()

    def write_to_source(self, data):
        self.request.sendall(data)

    def stop_forwarding(self):
        self.request.close()



def GetOFTypeName(ofop):
    return {
        0 : 'OF_HELLO',
        1 : 'OF_ERROR',
        2 : 'OF_ECHO_REQ',
        3 : 'OF_ECHO_RES',
        4 : 'OF_EXPERIMENTER',
        5 : 'OF_FEATURE_REQ',
        6 : 'OF_FEATURE_RES',
        7 : 'OF_GET_CONFIG_REQ',
        8 : 'OF_GET_CONFIG_RES',
        9 : 'OF_SET_CONFIG',
        10 : 'OF_PACKET_IN',
        11 : 'OF_FLOW_REMOVED',
        12 : 'OF_PORT_STATUS',
        13 : 'OF_PACKET_OUT',
        14 : 'OF_FLOW_MOD',
        15 : 'OF_GROUP_MOD',
        16 : 'OF_PORT_MOD',
        17 : 'OF_TABLE_MOD',
        18 : 'OF_MULTIPART_REQ',
        19 : 'OF_MULTIPART_RES',
        20 : 'OF_BARRIER_REQ',
        21 : 'OF_BARRIER_RES',
        22 : 'OF_QUEUE_GET_CONFIG_REQ',
        23 : 'OF_QUEUE_GET_CONFIG_RES',
        24 : 'OF_ROLE_REQ',
        25 : 'OF_ROLE_RES',
        26 : 'OF_GET_ASYNC_REQ',
        27 : 'OF_GET_ASYNC_RES',
        28 : 'OF_SET_ASYNC',
        29 : 'OF_METER_MOD',
    }.get(ofop, 'OF_UNKNOW')



def ParseRequestForOFop(request, source):
    request = binascii.hexlify(request)
    ptype = int(request[0:2], 16)
    ofop = int(request[2:4], 16)
    if ptype == 4:
        #print "Handled OF1.3 message "+str(ofop)
        if ofop==0 or ofop==10 or ofop==14:
            print "INFO    From "+source+" Handled OF13 type "+"{:2d}".format(ofop)+" - "+GetOFTypeName(ofop)
        return ofop
    return -1


def ParseFlowModRequestForAddress(request):
    request = binascii.hexlify(request)
    #144 = dummy flowmod len of odl-openflowplugin-droptest
    #if len(request) == 144:
    return request[112:124]
    #return ''

def ParsePacketInRequestForAddress(request):
    request = binascii.hexlify(request)
    if len(request) >= 108:
        return request[96:108]
    return ''


def ComputeOFopLatency(address, controller_ip):
    packet_in_ts = None
    try:
        packet_in_ts = OF_TEST_FLOWMOD_TS[address][0]
    except Exception, e:
        return -1
    if packet_in_ts != None:
        flow_mod_ts = time.time()
        del OF_TEST_FLOWMOD_TS[address]
        lt = flow_mod_ts - packet_in_ts
        lt = round(lt, 5)
        CSV_OUTPUT_WRITER.writerow([lt])
        CSV_OUTPUT_FILE.flush()
        LATENCY_MEASURES[controller_ip] = [lt] + LATENCY_MEASURES[controller_ip][:LATENCY_AVG_MEASURES_NUM-1]
        print "INFO    OFop latency update "+str(controller_ip)+":" + str(lt)+"s"
        print "INFO    OFop latency avg    "+str(controller_ip)+":" + str(ComputeOFopAvgLatency(controller_ip))+"s"
        return lt
    return -1

def ComputeOFopAvgLatency(controller_ip):
    return round(sum(LATENCY_MEASURES[controller_ip])/min(len(LATENCY_MEASURES[controller_ip]), LATENCY_AVG_MEASURES_NUM),4)


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    serverListeningPort = 6633

    def setListeningPortValue(self, listeningPort):
        self.serverListeningPort = listeningPort



if __name__ == "__main__":
    print '\n\n\n'
    FORWARDING_SCHEME = StaticForwarder()
    #FORWARDING_SCHEME = WardropForwarder()
    proxy = []
    proxyThread = []
    for i in range(CONTROLLERS_COUNT):
        print 'INFO    Setting up proxy socket server on 127.0.0.1:' + str(LB_PORTS[i])
        proxy.append(ThreadedTCPServer(('', LB_PORTS[i]), OFSouthboundRequestHandler))
        proxy[i].setListeningPortValue(LB_PORTS[i])
        proxyThread.append(threading.Thread(target=proxy[i].serve_forever))
        proxyThread[i].daemon = True
        proxyThread[i].start()
    print 'INFO    Handling requests, press <Ctrl-C> to quit\n'
    try:
        while True:
            sleep(1)
    except:
        pass
    print "\nINFO    Shutdown, wait..."
    print "INFO    Bye!\n"
    CSV_OUTPUT_FILE.close()
    for i in range(CONTROLLERS_COUNT):
        proxy[i].shutdown()
