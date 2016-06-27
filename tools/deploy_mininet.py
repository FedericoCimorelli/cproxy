#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, OVSKernelSwitch, OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.topo import Topo
from functools import partial
import random
import re
import time


CONTROLLERS_IPS = ['127.0.0.1']
CONTROLLERS_PORTS = [6634, 6635, 6636]
NUM_SWITCHES = 1
NUM_HOST_PER_SWITCH = 2 #at least 2!!
PACKETS_GEN_DURATION = 10


class MultiSwitch( OVSKernelSwitch ):
    "Custom Switch() subclass that connects to all the controllers"
    def start( self, controllers ):
        return OVSKernelSwitch.start( self, controllers )


class DisconnectedTopology(Topo):
    def build(self):
        switch_num_name = 1
        for i in range(NUM_SWITCHES):
            switch_name = 's' + str(switch_num_name)
            time.sleep(0.5)
            print 'Adding switch ' + str(switch_name)
            switch = self.addSwitch(switch_name, cls=OVSKernelSwitch, protocols='OpenFlow13')
            host_num_name = 1
            for j in range(NUM_HOST_PER_SWITCH):
                time.sleep(0.5)
                print 'Adding host ' + 's'+str(switch_num_name)+'h'+str(host_num_name)
                host = self.addHost('s'+str(switch_num_name)+'h'+str(host_num_name))
                #switch.linkTo(host)
                time.sleep(0.05)
                self.addLink(host, switch)
                host_num_name = host_num_name + 1
            switch_num_name = switch_num_name + 1



def DeployOF13Network():
   MultiSwitch13 = partial( MultiSwitch, protocols='OpenFlow13' )
   #topology = TreeTopo(depth=2,fanout=2)
   topology = DisconnectedTopology()
   net = Mininet(controller=RemoteController, topo=topology, switch=MultiSwitch13, build=False, autoSetMacs=True)
   info( '*** Adding controllers\n')
   c1 = net.addController('c1', controller=RemoteController, ip=CONTROLLERS_IPS[0], port=CONTROLLERS_PORTS[0])
   #c1 = net.addController('c1', controller=RemoteController, ip="192.168.56.102", port=6633)
   #c2 = net.addController('c2', controller=RemoteController, ip=CONTROLLERS_IPS[0], port=CONTROLLERS_PORTS[1])
   #c3 = net.addController('c3', controller=RemoteController, ip=CONTROLLERS_IPS[0], port=CONTROLLERS_PORTS[2])
   info( '*** Starting network\n')
   net.build()
   info( '*** Starting controllers\n')
   c1.start()
   #c2.start()
   #c3.start()
   #info( '*** Starting switches\n')
   #s1.start([c1,c2,c3])
   net.start()
   #net.staticArp()
   #   i = 0;
   #   while i < 10:
   #     h1, h2  = random.choice(net.hosts), random.choice(net.hosts)
   #     print h1.IP(), "-->", h2.IP()
   #     sent, received, rttmin, rttavg, rttmax, rttdev = ping(h1, h2)
   #     print received,"/",sent
   #     i = i + 1
   #     sleep(1)
   print 'Waiting for handshake end...'
   time.sleep(10) #wait for handshake end...
   detect_hosts(net, ping_cnt=50)
   generate_traffic(net)
   #CLI( net )
   print '\nOF traffic generated'
   print 'Waiting, then clean...\n'
   time.sleep(10) #wait for handshake end...
   net.stop()


def detect_hosts(net, ping_cnt=50):
    i = 0
    print '\nSending ping from all hosts, in progress'
    for host in net.hosts:
        host.sendCmd(str(host) + 'ping -c {0} {1}'.format(str(ping_cnt), str(CONTROLLERS_IPS[0])))
        host.waitOutput()
    print 'Sending ping from all hosts, done\n'


def generate_mac_address_pairs(current_mac):
    base_mac = 0x11000000000000
    generated_mac = hex(base_mac + int(current_mac, 16))
    source_mac = ':'.join(''.join(pair) for pair in zip(*[iter(hex(int(generated_mac, 16) + 1))]*2))[6:]
    dest_mac = ':'.join(''.join(pair) for pair in zip(*[iter(hex(int(generated_mac, 16) + 2))]*2))[6:]
    return source_mac, dest_mac


def generate_traffic(net):
    interpacket_delay_ms = 1000 #1sec
    traffic_transmission_delay = interpacket_delay_ms / 1000
    transmission_start = time.time()
    last_mac = hex(int('00000000', 16) + 0xffffffff)
    current_mac = hex(int(last_mac, 16) - 0x0000ffffffff + 0x000000000001)
    message_count = 0
    print "Test duration: " + str(PACKETS_GEN_DURATION)

    for s in net.switches:
        s.sendCmd('sudo ovs-ofctl del-flows ' + str(s))

    while (time.time() - transmission_start) <= PACKETS_GEN_DURATION:
        for host_index in range(len(net.hosts)):
            print 'Test in progress ' + str((time.time()-transmission_start)/PACKETS_GEN_DURATION*100)[:4]+'%'
            src_mac, dst_mac = generate_mac_address_pairs(current_mac)
            current_mac = hex(int(current_mac, 16) + 2)
            net.hosts[host_index].sendCmd('sudo mz -a {0} -b {1} -t arp'.format(src_mac, dst_mac))
            message_count+=1
            print 'PACKET_IN [arp {0} > {1}]'.format(src_mac, dst_mac)
            time.sleep(0.3)
        #time.sleep(traffic_transmission_delay)
        print 'Waiting for hosts output'
        for host in net.hosts:
            host.waitOutput()
        if int(current_mac, 16) >= int(last_mac, 16):
            current_mac = hex(int(last_mac, 16) - 0x0000ffffffff + 0x000000000001)
            # The minimum controller hard_timeout is 1 second.
            # Retransmission using the init_mac must start after the
            # minimum hard_timeout interval
            #if (time.time - transmission_start) < 1:
            #    time.sleep(1 - (time.time - transmission_start))
            #    print 'WWWWWWWWWWW'

    print '\n**************************\nSend '+ str(message_count) +' OF PACKET_IN in ' + str(PACKETS_GEN_DURATION) + "seconds"
    print 'Avg ' + str(message_count/PACKETS_GEN_DURATION) + 'msg/sec\n*********************\n'
    # Cleanup hosts console outputs and write flags after finishing
    # transmission
    for host in net.hosts:
        host.waitOutput()



if __name__ == '__main__':
    setLogLevel( 'info' )
    DeployOF13Network()
