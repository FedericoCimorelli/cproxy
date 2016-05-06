import socket
import SocketServer
import threading
from struct import *
import binascii
from time import sleep

LISTENING_HOST = ""
LISTENING_PORTS = [6634, 6635, 6636]
TARGET_PORT = 6633
TARGET_HOSTS = ['127.0.0.1', '127.0.0.1', '127.0.0.1']


class Forwarder(threading.Thread):
    def __init__(self, source):
        threading.Thread.__init__(self)
        self.source = source
        self.dest = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.SOCK_STREAM)
        self.dest.connect((TARGET_HOSTS[0], TARGET_PORT))

    def run(self):
        print "starting forwarder... "

        try:
            while True:
                data = self.dest.recv(4096)
                ParseTCPpacket(data)
                if len(data) == 0:
                    raise Exception("endpoint closed")
                print "Received from dest: " + str(len(data))
                self.source.write_to_source(data)
        except Exception, e:
            print "EXCEPTION reading from forwarding socket"
            print e

        self.source.stop_forwarding()
        print "...ending forwarder."

    def write_to_dest(self, data):
        print "Sending to dest: " + str(len(data))
        self.dest.send(data)

    def stop_forwarding(self):
        print "...closing forwarding socket"
        self.dest.close()



class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        print "Starting to handle connection..."
        f = Forwarder(self)
        f.start()

        try:
            while True:
                data = self.request.recv(4096)
                if len(data) == 0:
                    raise Exception("endpoint closed")
                print "Received from source: " + str(len(data))
                f.write_to_dest(data)
        except Exception, e:
            print "EXCEPTION reading from main socket"
            print e

        f.stop_forwarding()
        print "...finishing handling connection"


    def write_to_source(self, data):
        print "Sending to source: " + str(len(data))
        self.request.send(data)

    def stop_forwarding(self):
        print "...closing main socket"
        self.request.close()

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass


def ParseTCPpacket(packet):
    print repr(packet)
    ip_header = packet[0:20]
    #now unpack them :)
    iph = unpack('!BBHHHBBH4s4s' , ip_header)
    version_ihl = iph[0]
    version = version_ihl >> 4
    ihl = version_ihl & 0xF
    iph_length = ihl * 4
    ttl = iph[5]
    protocol = iph[6]
    s_addr = socket.inet_ntoa(iph[8]);
    d_addr = socket.inet_ntoa(iph[9]);
    print 'Version : ' + str(version) + ' IP Header Length : ' + str(ihl) + ' TTL : ' + str(ttl) + ' Protocol : ' + str(protocol) + ' Source Address : ' + str(s_addr) + ' Destination Address : ' + str(d_addr)
    tcp_header = packet[iph_length:iph_length+20]
    #now unpack them :)
    tcph = unpack('!HHLLBBHHH' , tcp_header)
    source_port = tcph[0]
    dest_port = tcph[1]
    sequence = tcph[2]
    acknowledgement = tcph[3]
    doff_reserved = tcph[4]
    tcph_length = doff_reserved >> 4
    print 'Source Port : ' + str(source_port) + ' Dest Port : ' + str(dest_port) + ' Sequence Number : ' + str(sequence) + ' Acknowledgement : ' + str(acknowledgement) + ' TCP header length : ' + str(tcph_length)
    h_size = iph_length + tcph_length * 4
    data_size = len(packet) - h_size
    #get data from the packet
    data = packet[h_size:]
    print 'Data : ' + data



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
    try:
        while True:
            sleep(1)
    except:
        pass
    print "...servers stopping."
    server_one.shutdown()
    server_two.shutdown()
    server_three.shutdown()
