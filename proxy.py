#!/usr/bin/python
# port-forward-proxy
import socket
import select
import time
import sys


buffer_size = 4096
delay = 0.0001
forward_to = ('91.142.218.33', 80)
ports = [6634, 6635, 6636]
target_port = 6633
servers = []


class Forward:
    def __init__(self):
        self.forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self, host, port):
        try:
            self.forward.connect((host, port))
            return self.forward
        except Exception, e:
            print e
            return False

class TheServer:
    input_list = []
    channel = {}

    def __init__(self):
        for p in ports:
            ds = ('', p)
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(ds)
            server.listen(200)
            servers.append(server)



    def main_loop(self):
        #self.input_list.append(self.server)
        while 1:
            time.sleep(delay)
            ss = select.select
            inputready, outputready, exceptready = ss(servers, [], [])
            for self.s in inputready:

                if self.s == servers[0]:
                    self.on_accept(0)
                    break
                if self.s == servers[1]:
                    self.on_accept(1)
                    break
                if self.s == servers[2]:
                    self.on_accept(2)
                    break

                self.data = self.s.recv(buffer_size)
                if len(self.data) == 0:
                    self.on_close()
                    break
                else:
                    self.on_recv()

# This method creates a new connection with the original target
# (proxy -> remote server), and accepts the current client connection
# (client->proxy). Both sockets are stored in input_list, to be then handled
# by main_loop. A "channel" dictionary is used to associate the
# endpoints(client<=>server).
    def on_accept(self, port):
        forward = Forward().start(forward_to[0], forward_to[1])
        clientsock, clientaddr = servers[port].accept()
        if forward:
            print clientaddr, "has connected"
            self.input_list.append(clientsock)
            self.input_list.append(forward)
            self.channel[clientsock] = forward
            self.channel[forward] = clientsock
        else:
            print "Can't establish connection with remote server.",
            print "Closing connection with client side", clientaddr
            clientsock.close()

# Disables and removes the socket connection between the proxy and the original
# server and the one between the client and the proxy itself.
    def on_close(self):
        print self.s.getpeername(), "has disconnected"
        #remove objects from input_list
        self.input_list.remove(self.s)
        self.input_list.remove(self.channel[self.s])
        out = self.channel[self.s]
        # close the connection with client
        self.channel[out].close()  # equivalent to do self.s.close()
        # close the connection with remote server
        self.channel[self.s].close()
        # delete both objects from channel dict
        del self.channel[out]
        del self.channel[self.s]

# This method is used to process and forward the data to the original
# destination ( client <- proxy -> server ).
    def on_recv(self):
        data = self.data
        # here we can parse and/or modify the data before send forward
        #print data
        self.channel[self.s].send(data)




if __name__ == '__main__':
        print "\n\n\n\n\n"
        print "----------------------------------------------------------------"
        print "--------------------  PORT-FORWARDING PROXY  -------------------"
        print "----------------------------------------------------------------"
        print "Listeing on " + str(ports) + " ports"
        print "Forwarding to " + str(target_port) + " port"
        print "----------------------------------------------------------------\n"

        server = TheServer()
        try:
            server.main_loop()
        except KeyboardInterrupt:
            print "Ctrl C - Stopping server"
            sys.exit(1)
