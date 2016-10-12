from __future__ import division
from random import randint
import socket
import SocketServer
import threading
import binascii
from time import sleep
import time
from collections import defaultdict
import csv
#from termcolor import colored

###############################
## requirements:             ##
## sudo apt-get install mz   ##
###############################


CSV_FILE_NAME = ['output1.csv', 'output2.csv', 'output3.csv']
CSV_OUTPUT_FILE1 = open(CSV_FILE_NAME[0], 'wb')
CSV_OUTPUT_FILE2 = open(CSV_FILE_NAME[1], 'wb')
CSV_OUTPUT_FILE3 = open(CSV_FILE_NAME[2], 'wb')
CSV_OUTPUT_WRITER1 = csv.writer(CSV_OUTPUT_FILE1)
CSV_OUTPUT_WRITER2 = csv.writer(CSV_OUTPUT_FILE2)
CSV_OUTPUT_WRITER3 = csv.writer(CSV_OUTPUT_FILE3)
LB_PORTS = [6634]
CONTROLLERS_PORT = 6633
CONTROLLERS_COUNT = 3
CONTROLLERS_IP = ['10.10.10.61', '10.10.10.62', '10.10.10.63']
MININET_IP = '10.10.10.66'
LATENCY_AVG_MEASURES_NUM = 5
LATENCY_MEASURES = defaultdict(list)
OF_TEST_FLOWMOD_TS =  []
OF_TEST_FLOWMOD_LATENCY = []
OF_REQ_FORWARDERS = []
#FORWARDING_SCHEME = None #Set it in main method

#WARDROP...
req_rate_tot = 1
req_rate = [1, 0, 0]  #tot reqs rate
probs = [1, 0, 0]   #tot =1
wardrop_threshold = 0.05
mu = 0.5
sigma = 0
wardrop_loop_time = 1 #1 sec

def initWardropForwarder():
    print "INFO    Wardrop Forwarder, initialization..."
    update()


def update():
    print "INFO    Wardrop Forwarder, req rate vector values " + format(req_rate)
    sigma = wardrop_threshold/((CONTROLLERS_COUNT-1)*req_rate_tot*mu)
    print "INFO    Wardrop Forwarder, sigma=" + str(sigma)
    for i in range(CONTROLLERS_COUNT):
        for j in range(CONTROLLERS_COUNT):
            if i!=j:    #6 case
                l = ComputeOFopAvgLatency(i) - ComputeOFopAvgLatency(j)
                print "INFO    Wardrop Forwarder, l"+str(CONTROLLERS_IP[i])+"-l"+str(CONTROLLERS_IP[j])+"="+str(l)
                if(l>wardrop_threshold):
                    req_rate_migr = req_rate[i]*sigma*l
                    print "INFO    Wardrop Forwarder, migrating "+str(req_rate_migr)+" reqs rate from "+str(CONTROLLERS_IP[i])+" to "+str(CONTROLLERS_IP[j])
                    req_rate[i] -= req_rate_migr
                    req_rate[j] -= req_rate_migr
                    print "INFO    Wardrop Forwarder, new req rate vector values " + format(req_rate)
                    probs[0] = req_rate[0]
                    probs[1] = req_rate[1]
                    probs[2] = req_rate[2]
                    print "INFO    Wardrop Forwarder, mapping req_rate vector to probs vector"
    threading.Timer(wardrop_loop_time, update).start()


def getControllerDestIndex():
    controllerIndex = probs.index(min(probs))
    print "INFO    Wardrop forwarder, controller index " + str(controllerIndex)
    return controllerIndex



def getStaticControllerIndexFromOFport(port):
    if port == LB_PORTS[0]:
        return 0
    if port == LB_PORTS[1]:
        return 1
    if port == LB_PORTS[2]:
        return 2



class OpenFlowRequestForwarder(threading.Thread):

    socket_to_odl_one = None
    serverListeningPort = 6633
    targetControllerIp_one = CONTROLLERS_IP[0]


    def __init__(self, client_address, serverListeningPort, targetControllerIp):
        threading.Thread.__init__(self)
        self.client_address = client_address
        self.serverListeningPort = serverListeningPort
        self.targetControllerIp = targetControllerIp
        self.socket_to_odl = None #was []
        print 'INFO    Setting OpenFlowRequestHandler socket from ' \
              + str(client_address.client_address) + ' to ' + str() + ':' + str(targetControllerIp)
        self.socket_to_odl = socket.socket(socket.AF_INET, socket.SOCK_STREAM)     
        try:
            self.socket_to_odl.connect((targetControllerIp, CONTROLLERS_PORT))
        except Exception, e:
            print e


    def run(self):
        try:
            while True:
                data = self.socket_to_odl.recv(65565)
                if len(data) == 0:
                    raise Exception("endpoint closed")
                if len(data) != 0:
                    source = str(self.socket_to_odl.getpeername()[0]) + ":" + str(self.socket_to_odl.getpeername()[1])
                    ofop = ParseRequestForOFop(data, source)
                    if ofop == 14: #FLOW_MOD
                        address = ParseFlowModRequestForAddress(data)
                        if address != '':
                            latency = UpdateOFopLatency(address, self.serverListeningPort)
                            #if FORWARDING_SCHEME.name == 'wardrop' and latency!=-1:
                            #    FORWARDING_SCHEME.update(self.socket_to_odl.getpeername(), latency)
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
        for i in range(CONTROLLERS_COUNT):
            print 'INFO    Setting OpenFlowRequestHandler socket from ' \
                  + str(MININET_IP) + ' to ' + str(CONTROLLERS_IP[i]) + ':' + str(CONTROLLERS_PORT)
            OFReqForwarders.append(OpenFlowRequestForwarder(self, self.server.serverListeningPort, CONTROLLERS_IP[i]))
            OFReqForwarders[i].start()
        try:
            while True:
                data = self.request.recv(65565)
                if len(data) == 0:
                    raise Exception("endpoint closed")
                if len(data) != 0:
                    ofop = ParseRequestForOFop(data, str(MININET_IP) + ':' + str(self.server.serverListeningPort))
                if ofop == 10: #on PACKET_IN
                    address = ParsePacketInRequestForAddress(data)
                    targetControllerIndex = getControllerDestIndex()
                    if address != '':
                        OFReqForwarders[targetControllerIndex].write_to_dest(data, ofop)
                        OF_TEST_FLOWMOD_TS.append((address, CONTROLLERS_IP[0], time.time()))
                else:
                    OFReqForwarders[0].write_to_dest(data, ofop)
                    OFReqForwarders[1].write_to_dest(data, ofop)
                    OFReqForwarders[2].write_to_dest(data, ofop)

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


def UpdateOFopLatency(address, controller_ip): #controller_port):
    packet_in_ts = None
    pt = CONTROLLERS_IP[0]
    #pt = LB_PORTS[0]
    try:
        for i in OF_TEST_FLOWMOD_TS:
            if i[0] == address:
                packet_in_ts = i[2]
                pt = i[1]
                #del (a, ts)
    except Exception, e:
        packet_in_ts = None
        return -1
    if packet_in_ts != None:
        flow_mod_ts = time.time()
        #del OF_TEST_FLOWMOD_TS[address]
        lt = flow_mod_ts - packet_in_ts
        lt = round(lt, 5)
        if pt == CONTROLLERS_IP[0]:
            LATENCY_MEASURES[0] = [lt] + LATENCY_MEASURES[0][:LATENCY_AVG_MEASURES_NUM - 1]
            CSV_OUTPUT_WRITER1.writerow([lt])
            CSV_OUTPUT_FILE1.flush()
        if pt == CONTROLLERS_IP[1]:
            LATENCY_MEASURES[1] = [lt] + LATENCY_MEASURES[1][:LATENCY_AVG_MEASURES_NUM - 1]
            CSV_OUTPUT_WRITER2.writerow([lt])
            CSV_OUTPUT_FILE2.flush()
        if pt == CONTROLLERS_IP[2]:
            LATENCY_MEASURES[2] = [lt] + LATENCY_MEASURES[2][:LATENCY_AVG_MEASURES_NUM - 1]
            CSV_OUTPUT_WRITER3.writerow([lt])
            CSV_OUTPUT_FILE3.flush()
        print "INFO    OFop latency update "+str(pt)+" " + str(lt)+" s"
        return lt
    return -1

def ComputeOFopAvgLatency(controller_ip):
    if len(LATENCY_MEASURES[controller_ip])>0 :
        return round(sum(LATENCY_MEASURES[controller_ip])/min(len(LATENCY_MEASURES[controller_ip]), LATENCY_AVG_MEASURES_NUM),5)
    return 0


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    serverListeningPort = 6633

    def setListeningPortValue(self, listeningPort):
        self.serverListeningPort = listeningPort



if __name__ == "__main__":
    print '\n\n\n'
    #FORWARDING_SCHEME = StaticForwarder()
    #FORWARDING_SCHEME = WardropForwarder()
    #FORWARDING_SCHEME = RoundRobinForwarder()
    initWardropForwarder()
    proxy = []
    proxyThread = []
    print 'INFO    Setting up proxy socket server on 127.0.0.1:' + str(LB_PORTS[0])
    proxy.append(ThreadedTCPServer(('', LB_PORTS[0]), OFSouthboundRequestHandler))
    proxy[0].setListeningPortValue(LB_PORTS[0])
    proxyThread.append(threading.Thread(target=proxy[0].serve_forever))
    proxyThread[0].daemon = True
    proxyThread[0].start()
    print 'INFO    Handling requests, press <Ctrl-C> to quit\n'
    try:
        while True:
            sleep(1)
    except:
        pass
    print "\nINFO    Shutdown, wait..."
    print "INFO    Bye!\n"
    CSV_OUTPUT_FILE1.close()
    CSV_OUTPUT_FILE2.close()
    CSV_OUTPUT_FILE3.close()
    proxy[0].shutdown()