#!/usr/bin/python
 
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.node import Controller 
from mininet.cli import CLI
from functools import partial
from mininet.node import RemoteController
import os
from threading import Timer


flag = True

# Topology: switches interconnected in diamond topology (3 parallel paths, no cross-links); 3 hosts on each side of the diamond

class MyTopo(Topo):
    "Single switch connected to n hosts."
    def __init__(self):
        Topo.__init__(self)
        s1=self.addSwitch('s1')
        s2=self.addSwitch('s2')
        s3=self.addSwitch('s3')
        s4=self.addSwitch('s4')
        s5=self.addSwitch('s5')
        h1=self.addHost('h1')
        h2=self.addHost('h2')
        h3=self.addHost('h3')
        h4=self.addHost('h4')
        h5=self.addHost('h5')
        h6=self.addHost('h6')

        h1_s1 = self.addLink(h1, s1, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        h2_s1 = self.addLink(h2, s1, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        h3_s1 = self.addLink(h3, s1, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        s1_s2 = self.addLink(s1, s2, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        s1_s3 = self.addLink(s1, s3, bw=1, delay='50ms', loss=0, max_queue_size=1000, use_htb=True)
        s1_s4 = self.addLink(s1, s4, bw=1, delay='100ms', loss=0, max_queue_size=1000, use_htb=True)
        s2_s5 = self.addLink(s2, s5, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        s3_s5 = self.addLink(s3, s5, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        s4_s5 = self.addLink(s4, s5, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        s5_h4 = self.addLink(s5, h4, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        s5_h5 = self.addLink(s5, h5, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        s5_h6 = self.addLink(s5, h6, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)

  print(self)




def perfTest():

    "Create network and run simple performance test"
    topo = MyTopo()
    #net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink, controller=POXcontroller1)
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink, controller=partial(RemoteController, ip='192.168.1.46', port=6633))
    net.start()

    print "Dumping host connections"
    dumpNodeConnections(net.hosts)
    h1,h2,h3=net.get('h1','h2','h3')
    h4,h5,h6=net.get('h4','h5','h6')
    h1.setMAC("0:0:0:0:0:1")
    h2.setMAC("0:0:0:0:0:2")
    h3.setMAC("0:0:0:0:0:3")
    h4.setMAC("0:0:0:0:0:4")
    h5.setMAC("0:0:0:0:0:5")
    h6.setMAC("0:0:0:0:0:6")

    s1, s2, s3 = net.get('s1', 's2', 's3')

    def changeDelayS1S2(delay):
       s1.cmdPrint('tc qdisc del dev s1-eth4 root')
       s1.cmdPrint('tc qdisc add dev s1-eth4 root handle 10: netem delay',delay)
       print '+++++++++++++ S1->S2',delay, 'delay started\n'



    t1=Timer(10, changeDelayS1S2, ['300ms'])
    t1.start()
    t2=Timer(20, changeDelayS1S2, ['10ms'])
    t2.start()
    t3=Timer(30, changeDelayS1S2, ['300ms'])
    t3.start()
    t4=Timer(40, changeDelayS1S2, ['10ms'])
    t4.start()


    CLI(net) # launch simple Mininet CLI terminal window
      

    net.stop()



if __name__ == '__main__':
    setLogLevel('info')
    perfTest()