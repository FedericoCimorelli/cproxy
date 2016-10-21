from __future__ import division
from random import randint
import socket
import SocketServer
import threading
import requests
import binascii
from time import sleep
import time
import random
from collections import defaultdict
import csv
#from termcolor import colored

###############################
## requirements:             ##
## sudo apt-get install mz   ##
###############################

CSV_OUTPUT_C_LATENCY = open('controllers_latency.csv', 'wb')
CSV_OUTPUT_WRITER_C_LATENCY = csv.writer(CSV_OUTPUT_C_LATENCY, dialect="excel")
CSV_OUTPUT_FLOWMOD_LATENCY_C1 = open('flowmod_latency_C1.csv', 'wb')
CSV_OUTPUT_WRITER_FLOWMOD_LATENCY_C1 = csv.writer(CSV_OUTPUT_FLOWMOD_LATENCY_C1, dialect="excel")
CSV_OUTPUT_FLOWMOD_LATENCY_C2 = open('flowmod_latency_C2.csv', 'wb')
CSV_OUTPUT_WRITER_FLOWMOD_LATENCY_C2 = csv.writer(CSV_OUTPUT_FLOWMOD_LATENCY_C2, dialect="excel")
CSV_OUTPUT_FLOWMOD_LATENCY_C3 = open('flowmod_latency_C3.csv', 'wb')
CSV_OUTPUT_WRITER_FLOWMOD_LATENCY_C3 = csv.writer(CSV_OUTPUT_FLOWMOD_LATENCY_C3, dialect="excel")
CSV_OUTPUT_WARDROP = open('wardrop.csv', 'wb')
CSV_OUTPUT_WRITER_WARDROP = csv.writer(CSV_OUTPUT_WARDROP, dialect="excel")
LB_PORTS = [6634]
CONTROLLERS_PORT = 6633
CONTROLLERS_COUNT = 3
CONTROLLERS_IP = ['10.10.10.61', '10.10.10.62', '10.10.10.63']
MININET_IP = '10.10.10.66'
LATENCY_AVG_MEASURES_NUM = 5
LATENCY_MEASURES = defaultdict(list)
OF_TEST_FLOWMOD_TS =  []
OF_TEST_FLOWMOD_LATENCY = defaultdict(list)
OF_REQ_FORWARDERS = []

#WARDROP...
req_rate_tot = 3
req_rate = [1.5, 1, 0.5]  #tot reqs rate
probs = [0.9, 0.06, 0.04]   #tot =1
wardrop_threshold = 0.05
mu = 0.5
sigma = 0
latency_loop_time = 1 #1 sec
wardrop_loop_time = 1 #1 sec
ts_last_req_fw = [0, 0, 0]
ts_last_req_fw_THRESHOLD = 1 #sec


def initWardropForwarder():
    print "INFO    Wardrop Forwarder, initialization..."
    update()


def measureControllersLatency():
    lt1 = 0
    lt2 = 0
    lt3 = 0
    try:
        r = requests.get('http://' + CONTROLLERS_IP[0] + ':8181/restconf/config/config:services/')
        lt1 = round(r.elapsed.total_seconds(), 5)
        LATENCY_MEASURES[0] = [lt1] + LATENCY_MEASURES[0][:LATENCY_AVG_MEASURES_NUM - 1]
        r = requests.get('http://' + CONTROLLERS_IP[1] + ':8181/restconf/config/config:services/')
        lt2 = round(r.elapsed.total_seconds(), 5)
        LATENCY_MEASURES[1] = [lt2] + LATENCY_MEASURES[1][:LATENCY_AVG_MEASURES_NUM - 1]
        r = requests.get('http://' + CONTROLLERS_IP[2] + ':8181/restconf/config/config:services/')
        lt3 = round(r.elapsed.total_seconds(), 5)
        LATENCY_MEASURES[2] = [lt3] + LATENCY_MEASURES[2][:LATENCY_AVG_MEASURES_NUM - 1]
        CSV_OUTPUT_WRITER_C_LATENCY.writerow([str(lt1) + " " + str(lt2) + " " + str(lt3)])
        CSV_OUTPUT_C_LATENCY.flush()
    except Exception, e:
        print "ERROR    Controllers latency error"
        print e
    print "INFO    Controllers latency update " + str(lt1)+"s "+str(lt2)+"s "+str(lt3)+"s "


def update():
    #print "INFO    Wardrop Forwarder, req rate vector values " + format(req_rate)
    sigma = wardrop_threshold/((CONTROLLERS_COUNT-1)*req_rate_tot*mu)
    #print "INFO    Wardrop Forwarder, sigma=" + str(sigma)
    for i in range(CONTROLLERS_COUNT):
        for j in range(CONTROLLERS_COUNT):
            if i!=j:    #6 case
                l = ComputeOFopAvgLatency(CONTROLLERS_IP[i]) - ComputeOFopAvgLatency(CONTROLLERS_IP[j])
                #print "INFO    Wardrop Forwarder, l"+str(CONTROLLERS_IP[i])+"-l"+str(CONTROLLERS_IP[j])+"="+str(l)
                if(l>wardrop_threshold):
                    req_rate_migr = req_rate[i]*sigma*l
                    print "INFO    Wardrop Forwarder, migrating "+str(req_rate_migr)+" reqs rate from "+str(CONTROLLERS_IP[i])+" to "+str(CONTROLLERS_IP[j])
                    req_rate[i] -= req_rate_migr
                    req_rate[j] += req_rate_migr
                    print "INFO    Wardrop Forwarder, new req rate vector values " + format(req_rate)
                    probs[0] = req_rate[0]/req_rate_tot
                    probs[1] = req_rate[1]/req_rate_tot
                    probs[2] = req_rate[2]/req_rate_tot
                    print "INFO    Wardrop Forwarder, mapping req_rate vector to probs vector" + format(probs)
                    r = str(probs[0])+" "+str(probs[1])+" "+str(probs[2])+" "+str(l)+" "+str(req_rate_migr)
                    CSV_OUTPUT_WRITER_WARDROP.writerow(r)
                    CSV_OUTPUT_WARDROP.flush()
    #measureControllersLatency()
    threading.Timer(wardrop_loop_time, update).start()


def getControllerDestIndex():
    #controllerIndex = probs.index(max(probs))
    rnd = random.random()
    controllerIndex = 0
    if rnd <= probs[0]:
        controllerIndex = 0
    else:
        if rnd <= probs[0] + probs[1]:
            controllerIndex = 1
        else:
            controllerIndex = 2
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
                        UpdateOFopLatency(address, self.socket_to_odl.getpeername()[0])
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
                        OF_TEST_FLOWMOD_TS.append((address, CONTROLLERS_IP[targetControllerIndex], time.time()))
                        ts_last_req_fw[targetControllerIndex] = time.time()
                        OFReqForwarders[targetControllerIndex].write_to_dest(data, ofop)
                    ############################################
                    #In order to update OFop controllers latency
                    #It uses the same source address, check consistency...
                    for i in range(0, CONTROLLERS_COUNT):
                        if time.time() - ts_last_req_fw[i] > ts_last_req_fw_THRESHOLD:
                            print "INFO    Forwarding also to "+str(CONTROLLERS_IP[i])+" to force latency update AAAAAAAAAAAAAAAAAAAAAAAaa"
                            ts_last_req_fw[i] = time.time()
                            OFReqForwarders[i].write_to_dest(data, ofop)
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
    return request[112:124]

def ParsePacketInRequestForAddress(request):
    request = binascii.hexlify(request)
    if len(request) >= 108:
        return request[96:108]
    return ''


def UpdateOFopLatency(address, controller_ip): #controller_port):
    packet_in_ts = None
    pt = CONTROLLERS_IP[0]
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
        OF_TEST_FLOWMOD_LATENCY[pt] = [lt] + OF_TEST_FLOWMOD_LATENCY[pt][:LATENCY_AVG_MEASURES_NUM -1]
        if pt == CONTROLLERS_IP[0]:
            CSV_OUTPUT_WRITER_FLOWMOD_LATENCY_C1.writerow(str(pt))
            CSV_OUTPUT_FLOWMOD_LATENCY_C1.flush()
        if pt == CONTROLLERS_IP[1]:
            CSV_OUTPUT_WRITER_FLOWMOD_LATENCY_C2.writerow(str(pt))
            CSV_OUTPUT_FLOWMOD_LATENCY_C2.flush()
        if pt == CONTROLLERS_IP[2]:
            CSV_OUTPUT_WRITER_FLOWMOD_LATENCY_C3.writerow(str(pt))
            CSV_OUTPUT_FLOWMOD_LATENCY_C3.flush()
        return lt
    return -1

def ComputeOFopAvgLatency(controller_ip):
    #using the controllers latency
    #if len(LATENCY_MEASURES[controller_ip])>0 :
    #    return round(sum(LATENCY_MEASURES[controller_ip])/min(len(LATENCY_MEASURES[controller_ip]), LATENCY_AVG_MEASURES_NUM),5)

    # using the OF ops controllers latency
    if len(OF_TEST_FLOWMOD_LATENCY[controller_ip]) > 0 :
        return round(sum(OF_TEST_FLOWMOD_LATENCY[controller_ip])/min(len(OF_TEST_FLOWMOD_LATENCY[controller_ip]), LATENCY_AVG_MEASURES_NUM),5)
    return 0



class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    serverListeningPort = 6633

    def setListeningPortValue(self, listeningPort):
        self.serverListeningPort = listeningPort



if __name__ == "__main__":
    print '\n\n\n'
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
    proxy[0].shutdown()
    CSV_OUTPUT_FLOWMOD_LATENCY_C1.close()
    CSV_OUTPUT_FLOWMOD_LATENCY_C2.close()
    CSV_OUTPUT_FLOWMOD_LATENCY_C3.close()
    CSV_OUTPUT_WARDROP.close()