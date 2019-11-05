#!/usr/bin/python
import socket as sk
import logging
import threading as th
import Queue
import os
import select, socket, sys
import time
import signal
import linuxcnc
import linuxcnc_util
import hal
from enum import Enum
import math
import fcntl
import struct
from threading import Timer
from opcua import ua, uamethod, Server

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


#Host=get_ip_address("br0")
Host="0.0.0.0"
Port=12346
running = 1



# The color which well be catched
# 0 : Red
# 1 : Green
# 2 : Yellow
# 3 : Blue


color=0
color_str=["Red", "Green", "Yellow", "Blue"]
switch_test="0"
wifi_lost_num=0

class switch_status(object):
    def __init__(self, interval, callback, *args, **kwargs):
	self._timer     = None
	self.interval   = interval
	self.args       = args
	self.kwargs     = kwargs
	self.callback   = callback
	self.is_running = False
	self._delays = 0
        self.start()

    def _run(self):
	if self._delays > 0:
	        self.is_running = False				
	        self.start()
		self._delays -= 1
	else:
		self.callback(*self.args, **self.kwargs)
	        self.is_running = False				
	
    def start(self):
        if not self.is_running:
            self.is_running = True
            self._timer = Timer(self.interval, self._run)
            self._timer.start()

    def stop(self):
        if self.is_running:
	    self._timer.cancel()
            self.is_running = False

    def delay(self,n = 1):
        self._delays = n
    
    def delay_clear(self,):
    	self._delays = 0

#sr.Microphone.list_microphone_names()

#r = sr.Recognizer()
#m = sr.Microphone()
#color_code = {u'\u7ea2' : 0, u'\u7eff' : 1, u'\u9ec4' : 2, u'\u84dd' : 3}

color_code = {u'red' : 0, u'green' : 1, u'yellow' : 2, u'blue' : 3}
def judge_which_color(s):
    for c in color_code.keys():
  #      for i in s:
  #          print i
  #          if c == i:
        if c in s:
                return color_code[c]
    return None



def exit_wakeup():
    global recog_status
    recog_status = 0
    print("Wait to wake up")


recog_status = 0 # no wake up
recog_status_handle = None
def speech_callback(r, audio):
    global color
    global recog_status
    global recog_status_handle
    print("got it!  Now to recognize it...")
    if recog_status == 0:
        try:
            str = r.recognize_sphinx(audio,keyword_entries=[("select", 0.8)],show_all=False)
            print("you said : ", str)
            if str[:6] == "select":
                recog_status = 1
                recog_status_handle = switch_status(40, exit_wakeup)
        except sr.UnknownValueError:
            print("Sphinx could not understand audio")
        except sr.RequestError as e:
            print("Sphinx error; {0}".format(e))
    else:
        try:
            #s = r.recognize_google(audio, language="zh")
            s = r.recognize_google(audio, language="en")
            print("Google Speech Recognition thinks you said:", s)
            col = judge_which_color(s)
            if col is None:
                print("Can not judge the color, so remain the %s" % color_str[color])
            else:
                color = col
                recog_status_handle.delay(2)
                print("Switch to color %s "% color_str[color])
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print("Could not request results from Google Speech Recognition service; {0}".format(e))
    if recog_status == 0:
        print("Wait to wake up... ")
    else:
        print("Waiting for speech instruction ... ")

#with m as source:
#    r.adjust_for_ambient_noise(source)

#r.dynamic_energy_threshold = False
#r.dynamic_energy_adjustment_damping = 0.1
#r.dynamic_energy_adjustment_ratio = 2
#r.energy_threshold = 800

#print("Wait to wake up... ")
#stop_listening = r.listen_in_background(m, speech_callback)

#Receive the blocks coordinates sending from OpenMV.
#Receive the set of the color we want to catch.
#Receive the thread over command.

def receive_coordinate (datq, sev, gev,pipe_r):
    global running
    global color
    global wifi_lost_num
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setblocking(0)
        server.bind((Host, Port))
    except:
        running=0
        exit(0)
    server.listen(1)
    inputs = [server, pipe_r]
    data_s = ""
    find_head = 0
    while inputs:
        readable, writable, exceptional = select.select(
            inputs,[], inputs)
        for s in readable:
            if s is server:
                connection, client_address = s.accept()
                connection.setblocking(0)
                inputs.append(connection)
            elif s is pipe_r:
                line = os.read(pipe_r, 64)
                if line:
                    if (line == 'q'):
                        try:
                            inputs[0].shutdown(socket.SHUT_RDWR)
                            inputs[0].close()
                            inputs[2].shutdown(socket.SHUT_RDWR)
                            inputs[2].close()
                        except:
                            pass
                        exit(0)
            else:
                data = s.recv(24)
                if data:
                    if data[0] == 'C': #set the color to filte 
                        if data[2:8] == 'Yellow':
                            color = 2
                        elif data[2:7] == 'Green':
                            color = 1
                        elif data[2:6] == 'Blue':
                            color = 3
                        elif data[2:5] == 'Red':
                            color = 0
                        else:
                            color = color
                    else:
                        wifi_lost_num = 0
                        data_s += data
                        print(data_s)
    		        if find_head == 0:
            	    	    index_h = data_s.find("S")
            	    	    if index_h >= 0:
                    		    find_head = 1
                    		    data_s = data_s[index_h:]
        	    	if find_head == 1:
            	    	    index_e = data_s.find("E")
            	    	    if index_e >= 0:
                    		find_head = 0
                        	if sev.isSet():
                        	    sev.clear()
                        	    datq.put(data_s[:index_e])
                        	    gev.set()
                    		data_s = data_s[index_e:]
                else:
                    inputs.remove(s)
                    s.close()
        for s in exceptional:
            inputs.remove(s)
            s.close()


class Uarm_states(Enum):
    START = 1
    DETECT = 2 
    SCAN = 3
    CONFIRM = 4
    DOWN = 5
    PUMP = 6
    REMOVE = 7

#    START   :  
#               1. Initiate the machine
#               2. Wait the switch down
#               3. Wait the swith up
#               4. Home the all joints
#               5. Set the machine on MDI model
#    DETECT : Check whether there are blocks on search area.  
#               1. Get all coordeinates finding on search area with specified by the color varable.
#               2. Map these coordeinates to machine coordinare system.
#               3. Map these coordenates to the corresponding scanning grids.
#               4. Return the grids mapped on step 3.
#    SCAN :   Scan all the grids returned on DETECT status
#               1. Move the camera to the first grid.
#               2. Get the coordeinates finding on this position
#               3. If finding a block and its coordeinate less then NEED_COMFIME, goto DOWN staus to catch.
#               4. If finding a block but its coordeinate great then NEED_COMFIME, goto CONFIRM staus.
#               5. If there isnot a block, and all the grids have been scanned, return DETECT staus, or move to next grid.
#               
#    CONFIRM :  If the coordeinate is too great, we need to move the camera to more close to this block to get a more exact coordeinate.
#               1. Move camera to the top of the coordeinate, and get new coordeinate.
#               2. If the new coordenate is effective, goto DOWN staus to catch, or return SCAN staus
#    DOWN    :  The below actions will complete the remove action. 
#    PUMP    :
#    REMOVE  :  



black_list={}
blacks_index = 0
#   (150, -180)  70     70        80       70         70    (150 , 180)
#           |-----------------------------------------------|
#           |         |         |       |         |         |
#           |    0    |    1    |    2  |    3    |    4    | 50
#           |         |         |       |         |         |
#           |-----------------------------------------------|
#           |         |         |       |         |         |
#           |    9    |    8    |    7  |    6    |    5    | 65
#           |         |         |       |         |         |
#           |-----------------------------------------------|
#           |         |         |       |         |         |
#           |    10   |   11    |   12  |   13    |   14    |  65
#           |         |         |       |         |         |
#           |-----------------------------------------------|

machine_grid = [[175,-145,140],[175,-45,140],[175, 0,140],[175,  45,140],[175, 145,140],
             [235, 145,140],[235, 45,140],[235, 0,140],[235, -45,140],[235,-145,140],
             [300,-145,140],[300,-45,140],[300, 0,140],[300,  45,140],[300, 145,140]]
scan_grid = []
c_step = 0
def map_to_grid(v, D=30):
    if not len(scan_grid):
        for i in machine_grid:
            a = math.atan2(i[1], i[0])
            scan_grid.append([i[0] - D*math.cos(a), i[1] - D*math.sin(a), i[2]])
    if v[0] < 200:
        i = 0
    elif v[0] > 265:
        i = 2
    else:
        i = 1

    if v[1] > 40:
        if v[1] > 110:
            j = 4
        else: 
            j = 3
    elif v[1] < -40:
        if v[1] < -110:
            j = 0
        else:
            j = 1
    else:
        j = 2

    k = i * 5 + j
    if k == 9:
        k = 5  
    elif k == 5:
        k = 9
    elif k == 8:
        k = 6
    elif k == 6:
        k = 8
    return k

# Some coordenates is not legal, so we could add them to black list to avoid checking it every time.  
def black_list_add(v, scan_pos):  
    global blacks_index
    black_list[blacks_index] = [v, c_step, scan_pos]
    blacks_index += 1

# If a coordenates in black list is not found within the last 3 times, remove it to black list.  
def black_list_update():
    global black_list
    for e in black_list.keys():
        if c_step - black_list[e][1] > 2:
            del black_list[e]

#Check whether a coordenates is in black list.
def black_list_check(v, scan_pos):
    global black_list
    for e in black_list.keys():
        if black_list[e][2] == scan_pos:
            v0=[[black_list[e][0][0], v[0]], [black_list[e][0][1], v[1]]]
            if is_almost_equal(v0):
                black_list[e][1] = c_step
                return True
    return False


#the format of the data coming from OpenMV:
#  data = "S:index*R.X:x1:Y:y1.X:x2:Y:y2/G.X:x1:Y:y1.X:x2:Y:y2/Y/B*R.X:x1:Y:y1.X:x2:Y:y2/G.X:x1:Y:y1.X:x2:Y:y2/Y/B"
#  The data was spilted into 3 segments by *:
#  1th segment:
#           'S'         : 'S' is the frame header
#           'index'     : 'index' is the number of this frame
#  2th and 3th segments are the coordeinates of all blocks found by MCU.
#  the difference between them is that they were found with two different thresholds.
#  The coordinates on 2th segment were found with a small threshold to find all blocks. It could be used on first step to find all blocks.
#  The one on 3th segment were found with a big threshold to get the exact position of the blocks.
#  2th or 3th segment:
#   R  : Red
#   G  : Green
#   Y  : Yellow
#   B  : Blue


def get_a_co(scan_pos=None ,segment_index=2 ,timeout=1, isConfirm = None):
    while (not datq.empty()):
        datq.get()
    gev.clear()
    sev.set()
    gev.wait(timeout)
    if not gev.isSet():
        return None
    try:
        data1=datq.get().split('*')
        data = data1[segment_index].split('/')[color].split('.')[1:]
    except:
        return None
    ret = []
    for dat in data:
        dat = dat.split(':')
        try:
            y = int(dat[1])   / -2.2  
            x = int(dat[3]) / -2.5
        except:
            continue

        if segment_index == 1:
            x = x / 0.6     
            y = y / 0.69
        if scan_pos is not None:
            if not black_list_check([x, y], scan_pos):
                ret.append([x, y])
            else:
                continue
        else:
            ret.append([x, y])
    if isConfirm is None:
        if len(ret):
            return ret[0]
        else:
            return None
    
    li = [math.pow(c[0], 2)+ math.pow(c[1], 2) for c in ret]
    if not len(li):
        return None
    return ret[li.index(min(li))]
    
def get_coordenate(scan_pos=None, isConfirm = None):
    time.sleep(1) 
    cos = [get_a_co(scan_pos, isConfirm=isConfirm) for i in range(3)]
    cos = filter(lambda c: c is not None, cos)
    if not len(cos) :
        return []
    
    if len(cos) < 3:
        cos += [get_a_co(scan_pos, isConfirm=isConfirm) for i in range(5)]
        cos = filter(lambda c: c is not None, cos)
    if len(cos) < 2:
        return []

    th = int(len(cos) * 2 / 3)
    for c in cos:
        li = [math.pow(c[0] - i[0],2) + math.pow(c[1] - i[1],2) for i in cos]
        if len(filter(lambda i: i < 25, li)) < th:
            cos.remove(c)
    if not len(cos):
        return []
    co = [0, 0]
    for c in cos:
        co[0] += c[0]
        co[1] += c[1]
    
    return [co[0]/ len(cos), co[1] / len(cos)]


def get_cos(segment_index=1, timeout=1):
    while (not datq.empty()):
        datq.get()
    gev.clear()
    sev.set()
    gev.wait(timeout)
    cos = []
    if not gev.isSet():
        print("no set")
        return []
    try:
        data=datq.get().split('*')
        data = data[segment_index].split('/')[color].split('.')[1:]
    except:
        print("data error")
        return []
    for dat in data:
        dat = dat.split(':')
        try:
            y = int(dat[1])   / -2.0  
            x = int(dat[3]) / -2.4
        except:
            print("data too small")
            continue

        if segment_index == 1:
            x = x * 1.5     
            y = y * 1.25
    	cos.append([x,y])
    return cos
	

def get_coordenates(segment_index=1, timeout=2):
    v = []
    time.sleep(1) 
    for i in range(3):
        v = v + get_cos(segment_index,timeout)
    return v




sev=th.Event()
gev=th.Event()
datq=Queue.Queue(2)
pipe_r,pipe_w = os.pipe()
get_co_thread = th.Thread(target=receive_coordinate,name="receive_coordinate",args=(datq, sev, gev, pipe_r))
get_co_thread.setDaemon(True)
get_co_thread.start()



h = hal.component("IO")

h.newpin("pump", hal.HAL_BIT, hal.HAL_OUT)
h.newpin("s_switch", hal.HAL_BIT, hal.HAL_IN)
h.newpin("s_pump", hal.HAL_BIT, hal.HAL_IN)
h.ready()
os.system("halcmd source ./postgui.hal")
h["pump"] = 1
c = linuxcnc.command()
s = linuxcnc.stat()
e = linuxcnc.error_channel()

uarm_state = Uarm_states.START

cnc_util=linuxcnc_util.LinuxCNC(command=c, status=s, error=e);

def estop_set(off):
    if (off):
        c.state(linuxcnc.STATE_ESTOP_RESET)
    else:
        c.state(linuxcnc.STATE_ESTOP)
    
def estop_get(isPoll=True):
    if (isPoll):
        s.poll()
    if (s.task_state == linuxcnc.STATE_ESTOP):
        return True
    else:
        return False


def machine_set(on, isPoll=True):
    if (isPoll):
        s.poll()
    if (on and s.task_state == linuxcnc.STATE_ESTOP_RESET):
        c.state(linuxcnc.STATE_ON)
    elif(not on and s.task_state == linuxcnc.STATE_ON):
        c.state(linuxcnc.STATE_OFF)
    
def machine_get(isPoll=True):
    if (isPoll):
        s.poll()
    if (s.task_state == linuxcnc.STATE_ON):
        return True
    else:
        return False

def unhome_joints(joints):
    for i in range(0,9):
        if joints[i]:
            c.unhome(i)
            c.wait_complete()

def task_mode_set(mode,isPoll=True):
    if (isPoll):
        s.poll()
    if s.task_mode == mode:
        return True
    c.mode(mode)
    c.wait_complete()

    
joints=[1,1,1,0,0,0,0,0,0]

def action_start():
    global uarm_state
    global switch_test
    estop_set(1)  # estop off
    machine_set(1)
    task_mode_set(linuxcnc.MODE_MANUAL)
    unhome_joints(joints)
    while h['s_switch']:
        time.sleep(0.5)
        pass

    while not h['s_switch']:
        time.sleep(0.5)
        pass

    switch_test = "1"
    for i in range(0,8):
        c.home(i)
    cnc_util.wait_for_home(joints, timeout=20)
    task_mode_set(linuxcnc.MODE_MDI)
    move_to([250, 0, 140])
    while h['s_switch']:
        time.sleep(0.5)
        v = get_coordenate()
        if len(v):
            print("test: ", get_machine_coordenate(v))
        pass
    uarm_state = Uarm_states.DETECT

def position_check(ver):
    if math.fabs(ver[1]) > 180:
        return False
    if ver[0] < 150:
        return False
    if ver[0] < 276: # math.cos(math.asin(180/330.0))*330 = 276
        return True

    r0 = math.cos(math.asin(ver[1] / 330)) * 330
    if ver[0] > r0:
        return False
    return True

def move_to(v, speed=5000, isBlock=True):
    c.mdi("g1 x" + "%f" % (v[0]) + " y" + "%f" % (v[1]) + " z"+ "%f" % (v[2]) + " f" + str(speed))
    if not isBlock:
        return True
    c.wait_complete()
    return True

def is_almost_equal(v, tolerance=5):
    for i in v:
        error = math.fabs(i[0] - i[1])
        if (error > tolerance):
            return False
    return True

def position_get(isPoll=True):
#    estop_set(1)  # estop off
    if (isPoll):
        s.poll()
    return [s.position[0:3], s.joint_actual_position[0:3]]


def co_calc(v, sin, cos, p, D=30, isComfirm=None, isDetect = None):
    if isComfirm is None:
        x=p[0][0] + D*cos + (v[0] ) *cos - (v[1] ) * sin
        y=p[0][1] + D*sin + (v[1] )* cos +  (v[0] ) * sin
    else:
        x=p[0][0]  + (v[0] ) *cos - (v[1] ) * sin
        y=p[0][1]  + (v[1] )* cos +  (v[0] ) * sin
    
    if isDetect is None:
        x -= 5
        y += 2.5
    else:
        x -= 10
        y += 5
    return [x,y]

def get_machine_coordenates(vs, p=None,isComfirm=None, isDetect = None):
    if p==None:
        p=position_get();
    cos = math.cos(p[1][0] * math.pi / 180)
    sin = math.sin(p[1][0] * math.pi / 180) 
    return [co_calc(v,sin,cos, p,isComfirm=isComfirm ,isDetect = isDetect) for v in vs]

def get_machine_coordenate(v, p=None, isComfirm=None, isDetect = None):
    if p==None:
        p=position_get();
    cos = math.cos(p[1][0] * math.pi / 180)
    sin = math.sin(p[1][0] * math.pi / 180)
    return co_calc(v, sin, cos, p, isComfirm=isComfirm, isDetect = isDetect)

de_top=220
de_speed=5000
de_pos={0:("g0",230,0,de_top, 10000), 
       1:("g1",  230, -40, de_top, de_speed),
       2:("g1",  230, 40, de_top, de_speed),
       3:("g1",  230, 0, de_top, de_speed),
       }
#de_pos={0:("g0",230,0,de_top, 10000), 
#       1:("g16", -10, de_speed),
#       2:("g16", 10, de_speed),
#       3:("g16", 0, de_speed),
#       }
de_step = 0
def detection_move():
    global de_step
    if de_pos[de_step][0] == 'g16':
        c.mdi("g16 r" + str(de_pos[de_step][1]) + " f" + str(de_pos[de_step][2]))
    else:
        c.mdi("g1 x" + str(de_pos[de_step][1]) + " y" + str(de_pos[de_step][2]) + " z" + str(de_pos[de_step][3]) + " f" + str(de_pos[de_step][4]))
    c.wait_complete()
    de_step = de_step + 1
    if de_step == len(de_pos):
        de_step = 1

scan_list=[]
detection_pos_return_to=[]
def action_detect():
    global uarm_state
    global scan_list
    global detection_pos_return_to
    global switch_test
    switch_test = "2"
    machine_list = []
    for i in range(len(de_pos) - 1):
        detection_move()
        co_list = get_coordenates(); 
        if (len(co_list)):
            p = position_get();
            machine_list += get_machine_coordenates(co_list, p)
    if len(machine_list):        
        scan_list_t = [map_to_grid(n) for n in machine_list]
        scan_list_t.sort()
        c=None
        for l in scan_list_t:
            if not c == l:
                c = l
                scan_list.append(c)
        detection_pos_return_to = p
        uarm_state=Uarm_states.SCAN
    else:
        uarm_state=Uarm_states.DETECT
    
down_pos = []
confirm_pos = []

def action_scan():
    global uarm_state
    global scan_list
    global down_pos
    global confirm_pos
    global c_step
    if not len(scan_list):
        move_to(detection_pos_return_to[0])
        uarm_state=Uarm_states.DETECT
        black_list_update()
        c_step = c_step + 1
        return

    scan_pos = scan_list[0]
    move_to(scan_grid[scan_pos]) 
    cor = get_coordenate(scan_pos)
    if not len(cor):
        scan_list.remove(scan_pos)
        uarm_state=Uarm_states.SCAN
        return

    if math.fabs(cor[0]) > 30 or math.fabs(cor[1]) > 30:
        x, y = get_machine_coordenate(cor, isComfirm=True)
        confirm_pos=[[x, y, scan_grid[scan_pos][2]], cor, scan_pos]
        uarm_state=Uarm_states.CONFIRM
    else:
        x, y = get_machine_coordenate(cor)
        if not position_check([x,y]):
            black_list_add(cor, scan_pos)
            uarm_state=Uarm_states.SCAN
        else:
            down_pos = [[x,y,scan_grid[scan_pos][2]], cor, scan_pos]
            uarm_state=Uarm_states.DOWN

def action_confirm():
    global uarm_state
    global confirm_pos
    global down_pos
    global switch_test
    switch_test = "3"
    move_to(confirm_pos[0])
    cor = get_coordenate(isConfirm=True)

    if not len(cor):
        black_list_add(confirm_pos[1], confirm_pos[2])
        uarm_state=Uarm_states.SCAN
        return
    
    if math.fabs(cor[0]) > 30 or math.fabs(cor[1]) > 30:
        x, y = get_machine_coordenate(cor, isComfirm=True)
        confirm_pos[0][0]=x
        confirm_pos[0][1]=y
        uarm_state=Uarm_states.CONFIRM
    else:
        x, y = get_machine_coordenate(cor)
        if not position_check([x,y]):
            black_list_add(confirm_pos[1], confirm_pos[2])
            uarm_state=Uarm_states.SCAN
        else:
            down_pos = [[x,y,confirm_pos[0][2]], confirm_pos[1], confirm_pos[2]]
            uarm_state=Uarm_states.DOWN

pump_top=35
def action_down():
    global uarm_state
    global switch_test
    switch_test = "4"

    move_to([down_pos[0][0], down_pos[0][1], pump_top], speed=20000)
    move_to([down_pos[0][0], down_pos[0][1], pump_top - 15],speed = 100, isBlock=False)
    while not h["s_pump"]:
        s.poll()
        print(h["s_pump"])
        if s.state == linuxcnc.RCS_DONE:
            break
    
    if h["s_pump"]:
        c.abort()
        c.wait_complete()
        uarm_state=Uarm_states.PUMP
    else: 
        black_list_add(down_pos[1], down_pos[2])
        uarm_state=Uarm_states.SCAN

def action_pump():
    global uarm_state
    global switch_test
    switch_test = "5"
    h['pump'] = 0
    time.sleep(1)
    uarm_state=Uarm_states.REMOVE


dump_pos=[[250, -210, pump_top],[200, -210, pump_top],[150, -210, pump_top] ]
dump_pos_index=0
dump_top = 100
def action_remove():
    global uarm_state
    global dump_pos_index
    global switch_test
    switch_test = "6"
    
    v=[down_pos[0][0],down_pos[0][1],dump_top]
    move_to(v, speed=16000)
    v=[dump_pos[dump_pos_index][0],dump_pos[dump_pos_index][1],160]
    move_to(v, speed=16000)
    move_to(dump_pos[dump_pos_index],speed = 2000 ,isBlock=False)
    while not h["s_pump"]:
        s.poll()
        if s.state == linuxcnc.RCS_DONE:
            break
    if h["s_pump"]:
        c.abort()
        c.wait_complete()

    h['pump']=1
    dump_pos_index += 1
    if dump_pos_index >= len(dump_pos):
        dump_pos_index=0
    time.sleep(3)
    move_to(v)
    uarm_state = Uarm_states.SCAN

states_switch = {
        Uarm_states.START       : action_start,
        Uarm_states.DETECT      : action_detect,
        Uarm_states.SCAN        : action_scan,
        Uarm_states.CONFIRM     : action_confirm,
        Uarm_states.DOWN        : action_down,
        Uarm_states.PUMP        : action_pump,
        Uarm_states.REMOVE      : action_remove,
}

def UARM_cmd_set(args):
    if (args[0] == 'switch'):
        return UARM_s.set_switch(args[1])
    if (args[0] == 'restart'):
        return UARM_s.restart()
    elif (args[0] == 'color'):
        return UARM_s.set_color(args[1])
    else:
        return "none"

def UARM_cmd_get(args):
    if (args[0] == 'switch'):
        return UARM_s.set_switch(args[1])
    elif (args[0] == 'color'):
        return UARM_s.set_color(args[1])
    elif (args[0] == 'estop'):
        return UARM_s.set_estop(args[1])
    else:
        return "none"

@uamethod
def command(parent, cmd):
    cmds = cmd.split(' ')
    if (cmds[0] == 'set'):
        ret = UARM_cmd_set(cmds[1:])
        return ret
    elif (cmds[0] == 'get'):
        return UARM_cmd_get(cmds[1:])
    else:
        return 'None'

server = Server()
server.set_endpoint("opc.tcp://%s:4843/uarm" % Host)
server.set_server_name("UARM service")
uri = "system service"
idx = server.register_namespace(uri)

######################################
#
# Create a new object for all linuxCNC.
#
#######################################
objects = server.get_objects_node()
UARM_obj = objects.add_object(idx, "UARM")

######################################
#
# Add command method
#
#######################################
inarg = ua.Argument()
inarg.Name = "cmd"
inarg.DataType = ua.NodeId(ua.ObjectIds.String)
inarg.ValueRank = -1
inarg.ArrayDimensions = []
inarg.Description = ua.LocalizedText("command")

outarg = ua.Argument()
outarg.Name = "resp"
outarg.DataType = ua.NodeId(ua.ObjectIds.String)
outarg.ValueRank = -1
outarg.ArrayDimensions = []
outarg.Description = ua.LocalizedText("result")

UARM_obj.add_method(idx, "command", command, [inarg], [outarg])

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False
def get_wifi_status():
    global wifi_lost_num
    if (wifi_lost_num > 2):
        return "1"
    else:
        wifi_lost_num += 1
        return "0"

class UARM_states:
    def __init__(self, obj, stat):
        self.obj = obj
        self.stat = stat
        self.position_0 = "0"
        self.position_1 = "0"
        self.position_2 = "0"
        self.joint_0 = "0"
        self.joint_1 = "0"
        self.joint_2 = "0"
        self.color = color_str[color]
        self.switch = switch_test
        self.wifi = get_wifi_status()
	self.pump = h["pump"]
        self.str_var = '{ "position_0" :  "%s",\
                           "position_1" :   "%s", \
                           "position_2" : "%s",\
                           "joint_0" : "%s",\
                           "joint_1" : "%s",\
                           "joint_2" : "%s",\
                           "color": "%s",\
                           "switch": "%s",\
                           "wifi": "%s",\
                           "pump": "%s"}'
        var = (self.position_0, self.position_1, self.position_2, self.joint_0, self.joint_1, self.joint_2, self.color, self.switch, self.wifi, self.pump)
        self.variable = obj.add_variable(idx, 'UARM_status', ua.Variant(self.str_var % var, ua.VariantType.String))
    def get_variable(self):
        var = (self.position_0, self.position_1, self.position_2, self.joint_0, self.joint_1, self.joint_2, self.color, self.switch, self.wifi, self.pump)
        return ua.Variant(self.str_var % var,ua.VariantType.String)
    def update(self):
	p = position_get()
        self.position_0 = p[0][0]
        self.position_1 = p[0][1]
        self.position_2 = p[0][2]
        self.joint_0 = p[1][0]
        self.joint_1 = p[1][1]
        self.joint_2 = p[1][2]
        self.color = color_str[color]
        self.wifi = get_wifi_status()
        self.switch = switch_test
        self.pump = h["pump"]
        self.variable.set_value(self.get_variable())
    def start(self):
        self.timer = RepeatedTimer(1,self.update)
        self.timer.start()

    def stop(self):
        self.timer.stop()
    
    def set_switch(self, s):
        global switch_test
        switch_test = s
    
    def set_color(self, s):
        global color
        color = color_str.index(s) 
    
    def set_estop(self, s):
        if s == "off":
            estop_set(1)
        else:
            estop_set(0)
    def restart(self):
        signal_exit_handler(1, "dump")

UARM_s = UARM_states(UARM_obj, s)	
UARM_s.start()
def signal_exit_handler(signum, frame):
    global pipe_w
    global get_co_thread
    global running
    os.write(pipe_w, 'q')
    get_co_thread.join()
    running = 0
    UARM_s.stop()

signal.signal(signal.SIGINT, signal_exit_handler)
server.start()
while(running):
    if h['s_switch']:
        uarm_state = Uarm_states.START
    print("uarm_state:", uarm_state)
    states_switch[uarm_state]()
server.stop()

