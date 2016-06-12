import socket
import SocketServer
import threading
import sys
from struct import *
import binascii
from time import sleep
import time
import requests
from collections import defaultdict


LISTENING_HOST = ""
#setup ovs switches according...
LB_PORTS = [6634, 6635, 6636]
CONTROLLERS_PORT = 6633
CONTROLLERS_IP = ['192.168.1.110', '1.1.1.1', '1.1.1.1']
MININET_IP = '127.0.0.1'

LATENCY_MEASURE_DELAY = 1 #sec
LATENCY_MEASERES_NUM = 10
TARGET_LATENCY_MEASURES = defaultdict()

OF_TEST_FLOWMOD_TS = defaultdict(list)
OF_TEST_FLOWMOD_LATENCY = []


class OpenFlowRequestHandler(threading.Thread):

    def __init__(self, client_address):
        threading.Thread.__init__(self)
        self.client_address = client_address
        #apply LB on this way, not reverse
        #assume that Mininet and LoadBalancer run on the same machine
        req_dest_port = CONTROLLERS_PORT
        req_dest_ip = CONTROLLERS_IP[0] #first odl
        if client_address.client_address[0] == CONTROLLERS_IP[0]: #come from the first odl
            req_dest_port = LB_PORTS[0]
            req_dest_ip = MININET_IP
        '''if client_address.client_address[0] == CONTROLLERS_IP[1]: #come from the second odl
            req_dest_port = LB_PORTS[1]
            req_dest_ip = MININET_IP
        if client_address.client_address[0] == CONTROLLERS_IP[2]: #come from the third odl
            req_dest_port = LB_PORTS[2]
            req_dest_ip = MININET_IP
        '''
        print 'INFO    Setting OpenFlowRequestHandler socket from '+str(client_address.client_address[0])+' to '+str(req_dest_ip)+':'+str(req_dest_port)
        self.dest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dest.connect((req_dest_ip, req_dest_port))


    def run(self):
        try:
            while True:
                data = self.dest.recv(65565)
                ofop = ParseRequestForOFop(data)
                if ofop == 14:
                    address = ParseFlowModRequestForAddress(data)
                    if address != '':
                        ComputeOFopLatency(address)
                if len(data) == 0:
                    raise Exception("endpoint closed")
                    #print 'Endpoint closed'
                self.client_address.write_to_source(data)
        except Exception, e:
            print "ERROR   Exception reading from forwarding socket"
            #print e
        self.client_address.stop_forwarding()

    def write_to_dest(self, data):
        self.dest.send(data)

    def stop_forwarding(self):
        self.dest.close()



class OFSouthboundLoadBalancerServer(SocketServer.StreamRequestHandler):

    def handle(self):
        print "INFO    Starting to handle connection..."
        f = OpenFlowRequestHandler(self)
        f.start()
        try:
            while True:
                data = self.request.recv(65565)
                ofop = ParseRequestForOFop(data)
                if ofop == 10: #on PACKET_IN
                    address = ParsePacketInRequestForAddress(data)
                    if address != '':
                        OF_TEST_FLOWMOD_TS[address].append(time.time())
                if len(data) == 0:
                    raise Exception("endpoint closed")
                #APPLY LB
                f.write_to_dest(data)
        except Exception, e:
            print "ERROR   Exception reading from main socket"
            #print e
        #f.stop_forwarding()

    def write_to_source(self, data):
        self.request.sendall(data)

    def stop_forwarding(self):
        self.request.close()



class MeasureLatenciesLooping():

    isRunning = False

    def __init__(self):
        for i in CONTROLLERS_IP:
            for j in range(1, LATENCY_MEASERES_NUM):
                TARGET_LATENCY_MEASURES[i].append(sys.maxint)
        #print TARGET_LATENCY_MEASURES.get(CONTROLLERS_IP[1])
        self.isRunning = True

    def stop(self):
        self.isRunning = False

    def runForever(self):
       while self.isRunning == True:
           for i in CONTROLLERS_IP:
               print "Measuring controller latency for "+i
               try:
                   r = requests.get('http://'+i+':8181/restconf/config/config:services/')
                   latency_measured = r.elapsed.total_seconds()
                   print str(r.elapsed.total_seconds()) +' sec'
                   TARGET_LATENCY_MEASURES[i] = [latency_measured] + TARGET_LATENCY_MEASURES[i][:LATENCY_MEASERES_NUM-1]
                   #print TARGET_LATENCY_MEASURES[i]
               except Exception, e:
                   print repr(e)
                   pass
           sleep(LATENCY_MEASURE_DELAY)



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
    }.get(ofop, 'UNKNOW')



def ParseRequestForOFop(request):
    request = binascii.hexlify(request)
    ptype = int(request[0:2], 16)
    ofop = int(request[2:4], 16)
    if ptype == 4:
        #print "Handled OF1.3 message "+str(ofop)
        print "INFO    Handled OF13 type "+"{:2d}".format(ofop)+" - "+GetOFTypeName(ofop)
        return ofop
    return -1


def ParseFlowModRequestForAddress(request):
    request = binascii.hexlify(request)
    #144 = dummy flowmod len of odl-openflowplugin-droptest
    if len(request) == 144:
        return request[112:124]
    return ''

def ParsePacketInRequestForAddress(request):
    request = binascii.hexlify(request)
    if len(request) >= 108:
        return request[96:108]
    return ''


def ComputeOFopLatency(address):
    packet_in_ts = OF_TEST_FLOWMOD_TS[address][0]
    if packet_in_ts != []:
        flow_mod_ts = time.time()
        del OF_TEST_FLOWMOD_TS[address]
        lt = flow_mod_ts - packet_in_ts
        OF_TEST_FLOWMOD_LATENCY.extend([lt])
        print "INFO    OF op latencies, last value: " + str(lt)
        #print OF_TEST_FLOWMOD_LATENCY
    else:
        print 'WARNING Compute OF op latency, corresponding PACKET_IN ts not found'


def GetAverageHostLatency(host):
    t = 0
    for i in TARGET_LATENCY_MEASURES[host]:
        t = t + i
    return t / LATENCY_MEASERES_NUM



class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    daemon_threads = True
    allow_reuse_address = True



if __name__ == "__main__":
    print '\n\n\n'
    print 'INFO    Setting up proxy daemon on ALL:'+str(LB_PORTS[0])
    proxy_one = ThreadedTCPServer(('', LB_PORTS[0]), OFSouthboundLoadBalancerServer)
    ip, port = proxy_one.server_address
    proxy_one_thread = threading.Thread(target=proxy_one.serve_forever)
    proxy_one_thread.daemon = True
    proxy_one_thread.start()
    '''
    print 'Setting up proxy daemon on ALL:'+str(CONTROLLERS_PORT)+' [reverse]'
    proxy_reverse = ThreadedTCPServer(('', CONTROLLERS_PORT), OFSouthboundLoadBalancerServer)
    ip, port = proxy_reverse.server_address
    proxy_reverse_thread = threading.Thread(target=proxy_reverse.serve_forever)
    proxy_reverse_thread.daemon = True
    proxy_reverse_thread.start()
    '''

    '''print 'Setting up proxy daemon for '+str(CONTROLLERS_IP[0])+':'+str(CONTROLLERS_PORT)
    proxy_one_reverse = ThreadedTCPServer(("", CONTROLLERS_PORT), OFSouthboundLoadBalancerServer)
    ip, port = proxy_one_reverse.server_address
    proxy_one_reverse_thread = threading.Thread(target=proxy_one_reverse.serve_forever)
    proxy_one_reverse_thread.daemon = True
    '''
    #proxy_one_reverse_thread.start()


    #server_two = ThreadedTCPServer((LISTENING_HOST, LB_PORTS[1]), OFSouthboundLoadBalancerServer)
    #server_three = ThreadedTCPServer((LISTENING_HOST, LB_PORTS[2]), OFSouthboundLoadBalancerServer)
    #ip, port = server_two.server_address
    #server_two_thread = threading.Thread(target=server_two.serve_forever)
    #server_two_thread.daemon = True
    #server_two_thread.start()
    #print "Server loop running on port ", port
    #ip, port = server_three.server_address
    #server_three_thread = threading.Thread(target=server_three.serve_forever)
    #server_three_thread.daemon = True
    #server_three_thread.start()
    #print "Server loop running on port ", port

    #latenciesMeasure = MeasureLatenciesLooping()
    #latenciesMeasureThread = threading.Thread(target = latenciesMeasure.runForever)
    #latenciesMeasureThread.start()
    #print "Latencies measure loop started"
    #print GetAverageHostLatency(CONTROLLERS_IP[1])

    print 'INFO    Handling requests, press <Ctrl-C> to quit\n\n\n'
    try:
        while True:
            sleep(1)
    except:
        pass
    print "\nINFO    Shutdown, wait..."
    print "INFO    Bye!\n"
    #latenciesMeasure.stop()
    proxy_one.shutdown()
    #proxy_reverse.shutdown()
    #proxy_one_reverse.shutdown()
    #server_two.shutdown()
    #server_three.shutdown()
