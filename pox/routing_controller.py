# The program implements a simple controller for a network with 6 hosts and 5 switches.
# The switches are connected in a diamond topology (without vertical links):
#    - 3 hosts are connected to the left (s1) and 3 to the right (s5) edge of the diamond.
# Overall operation of the controller:
#    - default routing is set in all switches on the reception of packet_in messages form the switch,
#    - then the routing for (h1-h4) pair in switch s1 is changed every one second in a round-robin manner to load balance the traffic through switches s3, s4, s2. 

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpidToStr
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.packet_base import packet_base
from pox.lib.packet.packet_utils import *
import pox.lib.packet as pkt
from pox.lib.recoco import Timer
from pox.openflow.of_json import *
import time
 
log = core.getLogger()
 
s1_dpid=0
s2_dpid=0
s3_dpid=0
s4_dpid=0
s5_dpid=0
 
s1_p1=0
s1_p4=0
s1_p5=0
s1_p6=0
s2_p1=0
s3_p1=0
s4_p1=0
 
pre_s1_p1=0
pre_s1_p4=0
pre_s1_p5=0
pre_s1_p6=0
pre_s2_p1=0
pre_s3_p1=0
pre_s4_p1=0

turn=0

mytimer = 0

intent_delay = 0.0
intent_host1 = 0
intent_host2 = 0

#######

s1_s2_delays = {
  "sent_time1": 0.0,
  "sent_time2": 0.0,
  "received_time1": 0.0,
  "received_time2": 0.0,
  "src_dpid": s1_dpid,
  "dst_dpid": s2_dpid,
  "mytimer":  0,
  "OWD1": 0.0,
  "OWD2": 0.0
}
s1_s3_delays = {
  "sent_time1": 0.0,
  "sent_time2": 0.0,
  "received_time1": 0.0,
  "received_time2": 0.0,
  "src_dpid": s1_dpid,
  "dst_dpid": s3_dpid,
  "mytimer":  0,
  "OWD1": 0.0,
  "OWD2": 0.0
}
s1_s4_delays = {
  "sent_time1": 0.0,
  "sent_time2": 0.0,
  "received_time1": 0.0,
  "received_time2": 0.0,
  "src_dpid": s1_dpid,
  "dst_dpid": s4_dpid,
  "mytimer":  0,
  "OWD1": 0.0,
  "OWD2": 0.0
}

s1_s2_delay = 0.0
s1_s3_delay = 0.0
s1_s4_delay = 0.0

dpid2_bytes = 0 
dpid3_bytes = 0
dpid4_bytes = 0

dpid2_packets = 0 
dpid3_packets = 0
dpid4_packets = 0

start_time = 0.0



#probe protocol packet definition; only timestamp field is present in the header (no payload part)
class myproto(packet_base):
  #My Protocol packet struct
  """
  myproto class defines our special type of packet to be sent all the way along including the link between the switches to measure link delays;
  it adds member attribute named timestamp to carry packet creation/sending time by the controller, and defines the 
  function hdr() to return the header of measurement packet (header will contain timestamp)
  """
  #For more info on packet_base class refer to file pox/lib/packet/packet_base.py

  def __init__(self):
     packet_base.__init__(self)
     self.timestamp=0

  def hdr(self, payload):
     return struct.pack('!I', self.timestamp)


 
def getTheTime():  #function to create a timestamp
  flock = time.localtime()
  then = "[%s-%s-%s" %(str(flock.tm_year),str(flock.tm_mon),str(flock.tm_mday))
  if int(flock.tm_hour)<10:
    hrs = "0%s" % (str(flock.tm_hour))
  else:
    hrs = str(flock.tm_hour)
  if int(flock.tm_min)<10:
    mins = "0%s" % (str(flock.tm_min))
  else:
    mins = str(flock.tm_min)
  if int(flock.tm_sec)<10:
    secs = "0%s" % (str(flock.tm_sec))
  else:
    secs = str(flock.tm_sec)
  then +="]%s.%s.%s" % (hrs,mins,secs)
  return then


def intent(delay, host1, host2):
  global intent_delay, intent_host1, intent_host2
  intent_delay = delay
  intent_host1 = host1
  intent_host2 = host2


def _timer_func ():
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid, turn

  #global start_time, sent_time1, sent_time2, src_dpid, dst_dpid
  global s1_s2_delays, s1_s3_delays, s1_s4_delays
  global s1_s2_delay, s1_s3_delay, s1_s4_delay
  global dpid2_bytes, dpid3_bytes, dpid4_bytes
  global dpid2_packets, dpid3_packets, dpid4_packets
  global start_time

  global intent_delay

  core.openflow.getConnection(s2_dpid).send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
  core.openflow.getConnection(s3_dpid).send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
  core.openflow.getConnection(s4_dpid).send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
  
  s1_s2_delays["src_dpid"] = s1_dpid
  s1_s2_delays["dst_dpid"] = s2_dpid
  s1_s3_delays["src_dpid"] = s1_dpid
  s1_s3_delays["dst_dpid"] = s3_dpid
  s1_s4_delays["src_dpid"] = s1_dpid
  s1_s4_delays["dst_dpid"] = s4_dpid


  ###### wysylanie pakietu mierzacego delay S1->S2
  #the following executes only when a connection to 'switch0' exists (otherwise AttributeError can be raised)
  if s1_s2_delays["src_dpid"] <>0 and not core.openflow.getConnection(s1_s2_delays["src_dpid"]) is None:	

    #send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
    core.openflow.getConnection(s1_s2_delays["src_dpid"]).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1_s2_delays["sent_time1"]=time.time() * 1000*10 - start_time #sending time of stats_req: ctrl => switch0

    #sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
    f = myproto() #create a probe packet object
    e = pkt.ethernet() #create L2 type packet (frame) object
    e.src = EthAddr("0:0:0:0:0:1")
    e.dst = EthAddr("0:0:0:0:0:6")
    e.type=0x5577 #set unregistered EtherType in L2 header type field, here assigned to the probe packet type 
    msg = of.ofp_packet_out() #create PACKET_OUT message object
    msg.actions.append(of.ofp_action_output(port=4)) #set the output port for the packet in switch0
    f.timestamp = int(time.time()*1000*10 - start_time) #set the timestamp in the probe packet
    e.payload = f
    msg.data = e.pack()
    core.openflow.getConnection(s1_s2_delays["src_dpid"]).send(msg)

  if s1_s2_delays["dst_dpid"] <>0 and not core.openflow.getConnection(s1_s2_delays["dst_dpid"]) is None:
    #send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
    core.openflow.getConnection(s1_s2_delays["dst_dpid"]).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1_s2_delays["sent_time2"]=time.time() * 1000*10 - start_time #sending time of stats_req: ctrl => switch1
  ######

  ###### wysylanie pakietu mierzacego delay S1->S3
  if s1_s3_delays["src_dpid"] <>0 and not core.openflow.getConnection(s1_s3_delays["src_dpid"]) is None:	

    #send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
    core.openflow.getConnection(s1_s3_delays["src_dpid"]).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1_s3_delays["sent_time1"]=time.time() * 1000*10 - start_time #sending time of stats_req: ctrl => switch0

    #sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
    f = myproto() #create a probe packet object
    e = pkt.ethernet() #create L2 type packet (frame) object
    e.src = EthAddr("0:0:0:0:0:1")
    e.dst = EthAddr("0:0:0:0:0:6")
    e.type=0x5577 #set unregistered EtherType in L2 header type field, here assigned to the probe packet type 
    msg = of.ofp_packet_out() #create PACKET_OUT message object
    msg.actions.append(of.ofp_action_output(port=5)) #set the output port for the packet in switch0
    f.timestamp = int(time.time()*1000*10 - start_time) #set the timestamp in the probe packet
    e.payload = f
    msg.data = e.pack()
    core.openflow.getConnection(s1_s3_delays["src_dpid"]).send(msg)

  if s1_s3_delays["dst_dpid"] <>0 and not core.openflow.getConnection(s1_s3_delays["dst_dpid"]) is None:
    #send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
    core.openflow.getConnection(s1_s3_delays["dst_dpid"]).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1_s3_delays["sent_time2"]=time.time() * 1000*10 - start_time #sending time of stats_req: ctrl => switch1
  ######

  ###### wysylanie pakietu mierzacego delay S1->S4
  if s1_s4_delays["src_dpid"] <>0 and not core.openflow.getConnection(s1_s4_delays["src_dpid"]) is None:	

    #send out port_stats_request packet through switch0 connection src_dpid (to measure T1)
    core.openflow.getConnection(s1_s4_delays["src_dpid"]).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1_s4_delays["sent_time1"]=time.time() * 1000*10 - start_time #sending time of stats_req: ctrl => switch0

    #sequence of packet formating operations optimised to reduce the delay variation of e-2-e measurements (to measure T3)
    f = myproto() #create a probe packet object
    e = pkt.ethernet() #create L2 type packet (frame) object
    e.src = EthAddr("0:0:0:0:0:1")
    e.dst = EthAddr("0:0:0:0:0:6")
    e.type=0x5577 #set unregistered EtherType in L2 header type field, here assigned to the probe packet type 
    msg = of.ofp_packet_out() #create PACKET_OUT message object
    msg.actions.append(of.ofp_action_output(port=6)) #set the output port for the packet in switch0
    f.timestamp = int(time.time()*1000*10 - start_time) #set the timestamp in the probe packet
    e.payload = f
    msg.data = e.pack()
    core.openflow.getConnection(s1_s4_delays["src_dpid"]).send(msg)
    #print "=====> probe sent: f=", f.timestamp, " after=", int(time.time()*1000*10 - start_time), " [10*ms]"

  #the following executes only when a connection to 'switch1' exists (otherwise AttributeError can be raised)
  if s1_s4_delays["dst_dpid"] <>0 and not core.openflow.getConnection(s1_s4_delays["dst_dpid"]) is None:
    #send out port_stats_request packet through switch1 connection dst_dpid (to measure T2)
    core.openflow.getConnection(s1_s4_delays["dst_dpid"]).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    s1_s4_delays["sent_time2"]=time.time() * 1000*10 - start_time #sending time of stats_req: ctrl => switch1
  ######



  #core.openflow.getConnection(s1_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  #core.openflow.getConnection(s2_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  #core.openflow.getConnection(s3_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  #core.openflow.getConnection(s4_dpid).send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
  #print getTheTime(), "sent the port stats request to s1_dpid"
  # below, routing in s1 towards h4 (IP=10.0.0.4) is set according to the value of the variable turn
  # turn controls the round robin operation
  # turn=0/1/2 => route through s2/s3/s4, respectively



  # load balacning:
  # defaultowo: round robin ze zmiana co 10 sekund
  
  # intent: jesli S1_S2 delay wiekszy niz 100 ms  wybieramy link z najmniejszym opoznieniem

  #load-balancer:
  #RR 0/1/2 10 / 50 / 100
  #       200/ 200/ 200

  #intent: jesli obecny link z RR > 200 to zmien na link z najmniejszym opoznieniem


  print turn
  print dpid2_packets, dpid3_packets, dpid4_packets
  if turn>=0 and turn<5:
      if s1_s2_delay > intent_delay:
        print "!!!!!! S1->S2 delay >", intent_delay, "ms !!!!!!"
        if s1_s3_delay < s1_s4_delay:
          print "------ S1->S3 ------"
          msg = of.ofp_flow_mod()
          msg.command=of.OFPFC_MODIFY_STRICT
          msg.priority =100
          msg.idle_timeout = 0
          msg.hard_timeout = 0
          msg.match.dl_type = 0x0800
          msg.match.nw_dst = "10.0.0.4"
          msg.actions.append(of.ofp_action_output(port = 5))
          core.openflow.getConnection(s1_dpid).send(msg)
          turn=turn+1
          return
        else:
          print "------ S1->S4 ------"
          msg = of.ofp_flow_mod()
          msg.command=of.OFPFC_MODIFY_STRICT
          msg.priority =100
          msg.idle_timeout = 0
          msg.hard_timeout = 0
          msg.match.dl_type = 0x0800
          msg.match.nw_dst = "10.0.0.4"
          msg.actions.append(of.ofp_action_output(port = 6))
          core.openflow.getConnection(s1_dpid).send(msg)
          turn=turn+1
          return

      print "------ S1->S2 ------"
      msg = of.ofp_flow_mod()
      msg.command=of.OFPFC_MODIFY_STRICT
      msg.priority =100
      msg.idle_timeout = 0
      msg.hard_timeout = 2
      msg.match.dl_type = 0x0800
      msg.match.nw_dst = "10.0.0.4"
      msg.actions.append(of.ofp_action_output(port = 4))
      core.openflow.getConnection(s1_dpid).send(msg)
      turn=turn+1
      return

  if turn>=5 and turn<10:
      if s1_s3_delay > intent_delay:
        print "!!!!!! S1->S3 delay >", intent_delay, "ms !!!!!!"
        if s1_s2_delay < s1_s4_delay:
          print "------ S1->S2 ------"
          msg = of.ofp_flow_mod()
          msg.command=of.OFPFC_MODIFY_STRICT
          msg.priority =100
          msg.idle_timeout = 0
          msg.hard_timeout = 0
          msg.match.dl_type = 0x0800
          msg.match.nw_dst = "10.0.0.4"
          msg.actions.append(of.ofp_action_output(port = 4))
          core.openflow.getConnection(s1_dpid).send(msg)
          turn=turn+1
          return
        else:
          print "------ S1->S4 ------"
          msg = of.ofp_flow_mod()
          msg.command=of.OFPFC_MODIFY_STRICT
          msg.priority =100
          msg.idle_timeout = 0
          msg.hard_timeout = 0
          msg.match.dl_type = 0x0800
          msg.match.nw_dst = "10.0.0.4"
          msg.actions.append(of.ofp_action_output(port = 6))
          core.openflow.getConnection(s1_dpid).send(msg)
          turn=turn+1
          return

      print "------ S1->S3 ------"
      msg = of.ofp_flow_mod()
      msg.command=of.OFPFC_MODIFY_STRICT
      msg.priority =100
      msg.idle_timeout = 0
      msg.hard_timeout = 0
      msg.match.dl_type = 0x0800
      msg.match.nw_dst = "10.0.0.4"
      msg.actions.append(of.ofp_action_output(port = 5))
      core.openflow.getConnection(s1_dpid).send(msg)
      turn=turn+1
      return

  if turn>=10 and turn<=15:
      if s1_s4_delay > intent_delay:
        print "!!!!!! S1->S4 delay >", intent_delay, "ms !!!!!!"
        if s1_s2_delay < s1_s3_delay:
          print "------ S1->S2 ------"
          msg = of.ofp_flow_mod()
          msg.command=of.OFPFC_MODIFY_STRICT
          msg.priority =100
          msg.idle_timeout = 0
          msg.hard_timeout = 0
          msg.match.dl_type = 0x0800
          msg.match.nw_dst = "10.0.0.4"
          msg.actions.append(of.ofp_action_output(port = 4))
          core.openflow.getConnection(s1_dpid).send(msg)
          turn=turn+1
          if turn==15: turn=0
          return
        else:
          print "------ S1->S3 ------"
          msg = of.ofp_flow_mod()
          msg.command=of.OFPFC_MODIFY_STRICT
          msg.priority =100
          msg.idle_timeout = 0
          msg.hard_timeout = 0
          msg.match.dl_type = 0x0800
          msg.match.nw_dst = "10.0.0.4"
          msg.actions.append(of.ofp_action_output(port = 5))
          core.openflow.getConnection(s1_dpid).send(msg)
          turn=turn+1
          if turn==15: turn=0
          return
      print "------ S1->S4 ------"
      msg = of.ofp_flow_mod()
      msg.command=of.OFPFC_MODIFY_STRICT
      msg.priority =100
      msg.idle_timeout = 0
      msg.hard_timeout = 0
      msg.match.dl_type = 0x0800
      msg.match.nw_dst = "10.0.0.4"
      msg.actions.append(of.ofp_action_output(port = 6))
      core.openflow.getConnection(s1_dpid).send(msg)
      turn=turn+1
      if turn==15: turn=0
      return



def _handle_flowstats_received (event):
  global dpid2_bytes, dpid3_bytes, dpid4_bytes
  global dpid2_packets , dpid3_packets , dpid4_packets 
  stats = flow_stats_to_list(event.stats)

  web_bytes = 0
  web_flows = 0
  web_packet = 0
  for f in event.stats:
    web_bytes += f.byte_count
    web_packet += f.packet_count
    web_flows += 1
  
  if event.connection.dpid==2:
    dpid2_packets = web_packet
  if event.connection.dpid==3:
    dpid3_packets = web_packet
  if event.connection.dpid==4:
    dpid4_packets = web_packet





def _handle_portstats_received (event):
  #Observe the handling of port statistics provided by this function.

  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  global s1_p1,s1_p4, s1_p5, s1_p6, s2_p1, s3_p1, s4_p1
  global pre_s1_p1,pre_s1_p4, pre_s1_p5, pre_s1_p6, pre_s2_p1, pre_s3_p1, pre_s4_p1

  global s1_s2_delays, s1_s3_delays, s1_s4_delays
  global start_time

  s1_s2_delays["received_time"] = time.time() * 1000*10 - start_time
  s1_s3_delays["received_time"] = time.time() * 1000*10 - start_time
  s1_s4_delays["received_time"] = time.time() * 1000*10 - start_time

  
  if event.connection.dpid==s1_dpid: # The DPID of one of the switches involved in the link
   
    s1_s2_delays["OWD1"]=0.5*(s1_s2_delays["received_time"] - s1_s2_delays["sent_time1"])
    s1_s3_delays["OWD1"]=0.5*(s1_s3_delays["received_time"] - s1_s3_delays["sent_time1"])
    s1_s4_delays["OWD1"]=0.5*(s1_s4_delays["received_time"] - s1_s4_delays["sent_time1"])

    for f in event.stats:
      if int(f.port_no)<65534:
        if f.port_no==1:
          pre_s1_p1=s1_p1
          s1_p1=f.rx_packets
          #print "s1_p1->","TxDrop:", f.tx_dropped,"RxDrop:",f.rx_dropped,"TxErr:",f.tx_errors,"CRC:",f.rx_crc_err,"Coll:",f.collisions,"Tx:",f.tx_packets,"Rx:",f.rx_packets
        if f.port_no==4:
          pre_s1_p4=s1_p4
          s1_p4=f.tx_packets
          #s1_p4=f.tx_bytes
          #print "s1_p4->","TxDrop:", f.tx_dropped,"RxDrop:",f.rx_dropped,"TxErr:",f.tx_errors,"CRC:",f.rx_crc_err,"Coll:",f.collisions,"Tx:",f.tx_packets,"Rx:",f.rx_packets
        if f.port_no==5:
          pre_s1_p5=s1_p5
          s1_p5=f.tx_packets
        if f.port_no==6:
          pre_s1_p6=s1_p6
          s1_p6=f.tx_packets
 
  if event.connection.dpid==s2_dpid:
     s1_s2_delays["OWD2"]=0.5*(s1_s2_delays["received_time"] - s1_s2_delays["sent_time2"])
  
     for f in event.stats:
       if int(f.port_no)<65534:
         if f.port_no==1:
           pre_s2_p1=s2_p1
           s2_p1=f.rx_packets
     print getTheTime(), "S1_p4(Sent):", (s1_p4-pre_s1_p4), "S2_p1(Received):", (s2_p1-pre_s2_p1)
 
  if event.connection.dpid==s3_dpid:
     s1_s3_delays["OWD2"]=0.5*(s1_s3_delays["received_time"] - s1_s3_delays["sent_time2"])
     for f in event.stats:
       if int(f.port_no)<65534:
         if f.port_no==1:
           pre_s3_p1=s3_p1
           s3_p1=f.rx_packets
     print getTheTime(), "S1_p5(Sent):", (s1_p5-pre_s1_p5), "S3_p1(Received):", (s3_p1-pre_s3_p1)

  if event.connection.dpid==s4_dpid:
     s1_s4_delays["OWD2"]=0.5*(s1_s4_delays["received_time"] - s1_s4_delays["sent_time2"])
     for f in event.stats:
       if int(f.port_no)<65534:
         if f.port_no==1:
           pre_s4_p1=s4_p1
           s4_p1=f.rx_packets
     print getTheTime(), "S1_p6(Sent):", (s1_p6-pre_s1_p6), "S4_p1(Received):", (s4_p1-pre_s4_p1)



def _handle_ConnectionUp (event):
  # waits for connections from all switches, after connecting to all of them it starts a round robin timer for triggering h1-h4 routing changes
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid
  print "ConnectionUp: ",dpidToStr(event.connection.dpid)
 
  #remember the connection dpid for the switch
  for m in event.connection.features.ports:
    if m.name == "s1-eth1":
      # s1_dpid: the DPID (datapath ID) of switch s1;
      s1_dpid = event.connection.dpid
      print "s1_dpid=", s1_dpid
    elif m.name == "s2-eth1":
      s2_dpid = event.connection.dpid
      print "s2_dpid=", s2_dpid
    elif m.name == "s3-eth1":
      s3_dpid = event.connection.dpid
      print "s3_dpid=", s3_dpid
    elif m.name == "s4-eth1":
      s4_dpid = event.connection.dpid
      print "s4_dpid=", s4_dpid
    elif m.name == "s5-eth1":
      s5_dpid = event.connection.dpid
      print "s5_dpid=", s5_dpid
 
  # start 1-second recurring loop timer for round-robin routing changes; _timer_func is to be called on timer expiration to change the flow entry in s1
  if s1_dpid<>0 and s2_dpid<>0 and s3_dpid<>0 and s4_dpid<>0 and s5_dpid<>0:
    Timer(1, _timer_func, recurring=True)






def _handle_PacketIn(event):
  global s1_dpid, s2_dpid, s3_dpid, s4_dpid, s5_dpid

  #global start_time, OWD1, OWD2
  global start_time
  global s1_s2_delays, s1_s3_delays, s1_s4_delays
  #global src_dpid, dst_dpid
  s1_s2_delays["received_time"] = (time.time() * 1000*10 - start_time)
  s1_s3_delays["received_time"] = (time.time() * 1000*10 - start_time)
  s1_s4_delays["received_time"] = (time.time() * 1000*10 - start_time)

  global s1_s2_delay, s1_s3_delay, s1_s4_delay

  
  

 
  packet=event.parsed


  ###### mierzenie i print delay dla S1->S2
  if packet.type==0x5577 and event.connection.dpid==s1_s2_delays["dst_dpid"]:
    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
    print "Delay of S",s1_s2_delays["src_dpid"], "->", "S", s1_s2_delays["dst_dpid"], "\n", int(s1_s2_delays["received_time"] - d - s1_s2_delays["OWD1"] - s1_s2_delays["OWD2"])/10, "[ms]"
    s1_s2_delay = (s1_s2_delays["received_time"] - d - s1_s2_delays["OWD1"] - s1_s2_delays["OWD2"])/10
    

  ###### mierzenie i print delay dla S1->S3
  if packet.type==0x5577 and event.connection.dpid==s1_s3_delays["dst_dpid"]:
    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
    print "Delay of S",s1_s3_delays["src_dpid"], "->", "S", s1_s3_delays["dst_dpid"], "\n", int(s1_s3_delays["received_time"] - d - s1_s3_delays["OWD1"] - s1_s3_delays["OWD2"])/10, "[ms]"
    s1_s3_delay = (s1_s3_delays["received_time"] - d - s1_s3_delays["OWD1"] - s1_s3_delays["OWD2"])/10

  ###### mierzenie i print delay dla S1->S4
  if packet.type==0x5577 and event.connection.dpid==s1_s4_delays["dst_dpid"]:
    c=packet.find('ethernet').payload
    d,=struct.unpack('!I', c)  # note that d,=... is a struct.unpack and always returns a tuple
    print "Delay of S",s1_s4_delays["src_dpid"], "->", "S", s1_s4_delays["dst_dpid"], "\n", int(s1_s4_delays["received_time"] - d - s1_s4_delays["OWD1"] - s1_s4_delays["OWD2"])/10, "[ms]"
    s1_s4_delay = (s1_s4_delays["received_time"] - d - s1_s4_delays["OWD1"] - s1_s4_delays["OWD2"])/10
  

  # Below, set the default/initial routing rules for all switches and ports.
  # All rules are set up in a given switch on packet_in event received from the switch which means no flow entry has been found in the flow table.
  # This setting up may happen either at the very first pactet being sent or after flow entry expirationn inn the switch
 
  if event.connection.dpid==s1_dpid:
     a=packet.find('arp')					# If packet object does not encapsulate a packet of the type indicated, find() returns None
     if a and a.protodst=="10.0.0.4":
       msg = of.ofp_packet_out(data=event.ofp)			# Create packet_out message; use the incoming packet as the data for the packet out
       msg.actions.append(of.ofp_action_output(port=4))		# Add an action to send to the specified port
       event.connection.send(msg)				# Send message to switch
 
     if a and a.protodst=="10.0.0.5":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=5))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.6":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=6))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.1":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=1))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.2":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=2))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.3":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=3))
       event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800		# rule for IP packets (x0800)
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.2"
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.3"
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.4"
     msg.actions.append(of.ofp_action_output(port = 4))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.5"
     msg.actions.append(of.ofp_action_output(port = 5))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.6"
     msg.actions.append(of.ofp_action_output(port = 6))
     event.connection.send(msg)
 
  elif event.connection.dpid==s2_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806		# rule for ARP packets (x0806)
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
  elif event.connection.dpid==s3_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
  
  elif event.connection.dpid==s4_dpid: 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 1
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
  
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0806
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 2
     msg.match.dl_type=0x0800
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
  elif event.connection.dpid==s5_dpid: 
     a=packet.find('arp')
     if a and a.protodst=="10.0.0.4":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=4))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.5":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=5))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.6":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=6))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.1":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=1))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.2":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=2))
       event.connection.send(msg)
 
     if a and a.protodst=="10.0.0.3":
       msg = of.ofp_packet_out(data=event.ofp)
       msg.actions.append(of.ofp_action_output(port=3))
       event.connection.send(msg)
     
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =10
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.in_port = 6
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
     
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.1"
     msg.actions.append(of.ofp_action_output(port = 1))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.2"
     msg.actions.append(of.ofp_action_output(port = 2))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.3"
     msg.actions.append(of.ofp_action_output(port = 3))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.4"
     msg.actions.append(of.ofp_action_output(port = 4))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.5"
     msg.actions.append(of.ofp_action_output(port = 5))
     event.connection.send(msg)
 
     msg = of.ofp_flow_mod()
     msg.priority =100
     msg.idle_timeout = 0
     msg.hard_timeout = 0
     msg.match.dl_type = 0x0800
     msg.match.nw_dst = "10.0.0.6"
     msg.actions.append(of.ofp_action_output(port = 6))
     event.connection.send(msg)

#As usually, launch() is the function called by POX to initialize the component (routing_controller.py in our case) 
#indicated by a parameter provided to pox.py 
import json
def launch ():
  global start_time
  d = json.load(open('/home/student/pox/client_intent.json'))
  intent(d['delay'], d['host1'], d['host2'])

  start_time = time.time() * 1000*10 # factor *10 applied to increase the accuracy for short delays (capture tenths of ms)
  print "start_time:", start_time/10
  

  core.openflow.addListenerByName("PortStatsReceived",_handle_portstats_received) # listen for port stats , https://noxrepo.github.io/pox-doc/html/#statistics-events
  core.openflow.addListenerByName("FlowStatsReceived",_handle_flowstats_received)
  core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
  core.openflow.addListenerByName("PacketIn",_handle_PacketIn)
 
