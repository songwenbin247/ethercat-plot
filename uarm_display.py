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

Host='10.5.5.1'
Port=12346
running = 1


# The color which well be catched
# 0 : Red
# 1 : Green
# 2 : Yellow
# 3 : Blue
color=0
color_str=["Red", "Green", "Yellow", "Blue"]

#Receive the blocks coordinates sending from OpenMV.
#Receive the set of the color we want to catch.
#Receive the thread over command.

def receive_coordinate (datq, sev, gev,pipe_r):
    global running
    global color
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
                        inputs[0].shutdown(socket.SHUT_RDWR)
                        inputs[2].shutdown(socket.SHUT_RDWR)
                        inputs[2].close()
                        inputs[0].close()
                        exit(0)
            else:
                data = s.recv(32)
                if data:
                    if data[0] == 'C': #set the color to filte 
                        print(data)
                        if data[2:8] == 'Yellow':
                            color = 2
                        elif data[2:7] == 'Green':
                            color = 1
                        elif data[2:6] == 'Blue':
                            color = 3
                        else:
                            color = 0
                        print("Switch the color to: %s" % color_str[color])
                    else:
 			data_s += data
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
def map_to_grid(v, D=25):
    if not len(scan_grid):
        for i in machine_grid:
            a = math.atan2(i[1], i[0])
            scan_grid.append([i[0] - D*math.cos(a), i[1] - D*math.sin(a), i[2]])
        print("scan_grid:", scan_grid)
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
    print("black_list_add ", v, scan_pos)

# If a coordenates in black list is not found within the last 3 times, remove it to black list.  
def black_list_update():
    global black_list
    for e in black_list.keys():
        if c_step - black_list[e][1] > 2:
            print("black_list_update", black_list[e])
            del black_list[e]

#Check whether a coordenates is in black list.
def black_list_check(v, scan_pos):
    global black_list
    print("black_check:", v)
    for e in black_list.keys():
        if black_list[e][2] == scan_pos:
            v0=[[black_list[e][0][0], v[0]], [black_list[e][0][1], v[1]]]
            if is_almost_equal(v0):
                print("black_check_ok", v)
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
        data=datq.get().split('*')
        data = data[segment_index].split('/')[color].split('.')[1:]
    except:
        return None
    
    print("get data:", data)
    ret = []
    for dat in data:
        dat = dat.split(':')
        try:
            y = int(dat[1])   / -2.0  
            x = int(dat[3]) / -2.4
        except:
            continue

        if segment_index == 1:
            x = x * 1.5     
            y = y * 1.25
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
    cos = [get_a_co(scan_pos, isConfirm=isConfirm) for i in range(10)]
    cos = filter(lambda c: c is not None, cos)
    if len(cos) < 3:
        return []

    th = int(len(cos) * 2 / 3)
    for c in cos:
        li = [math.pow(c[0] - i[0],2) + math.pow(c[1] - i[1],2) for i in cos]
        if len(filter(lambda i: i < 25, li)) < th:
            print("remove from cos", c)
            cos.remove(c)
    if not len(cos):
        return []
    print("cos", cos)
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
        return []
    data=datq.get().split('*')
    print("get data", data)
    data = data[segment_index].split('/')[color].split('.')[1:]
    for dat in data:
        dat = dat.split(':')
        try:
            y = int(dat[1])   / -2.0  
            x = int(dat[3]) / -2.4
        except:
            continue

        if segment_index == 1:
            x = x * 1.5     
            y = y * 1.25
    	cos.append([x,y])
    return cos
	

def get_coordenates(segment_index=1, timeout=3):
    v = []
    time.sleep(1) 
    for i in range(3):
        v = v + get_cos(segment_index,timeout)
    return v


def signal_exit_handler(signum, frame):
    global pipe_w
    global get_co_thread
    global running
    os.write(pipe_w, 'q')
    get_co_thread.join()
    running = 0


sev=th.Event()
gev=th.Event()
datq=Queue.Queue(2)
pipe_r,pipe_w = os.pipe()
get_co_thread = th.Thread(target=receive_coordinate,name="receive_coordinate",args=(datq, sev, gev, pipe_r))
get_co_thread.setDaemon(True)
get_co_thread.start()
signal.signal(signal.SIGINT, signal_exit_handler)



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
    estop_set(1)  # estop off
    machine_set(1)
    task_mode_set(linuxcnc.MODE_MANUAL)
    unhome_joints(joints)
    while h['s_switch']:
        pass
    while not h['s_switch']:
        pass
    for i in range(0,8):
        c.home(i)
    cnc_util.wait_for_home(joints, timeout=20)
    task_mode_set(linuxcnc.MODE_MDI)
    move_to([250, 0, 140])
    while h['s_switch']:
        pass
    uarm_state = Uarm_states.DETECT


R_MIN = 140
R_MAX = 330
R_MAX_2 = R_MAX * R_MAX
R_MIM_2 = R_MIN * R_MIN 

S_ANGLE_1 = 60 * math.pi / 180 
S_ANGLE_2 = 40 * math.pi / 180 
k = (math.cos(S_ANGLE_1) * R_MAX - math.cos(S_ANGLE_2) * R_MIN) / (math.sin(S_ANGLE_1) * R_MAX - math.sin(S_ANGLE_2) * R_MIN)
b = math.cos(S_ANGLE_1) * R_MAX - k * math.sin(S_ANGLE_1) * R_MAX 

def position_check(ver):
    r0 = math.atan2(ver[1] , ver[0])
    d2 = math.pow(ver[0], 2) + math.pow(ver[1], 2)
    if math.fabs(r0) > S_ANGLE_2:
        print("math.fabs(r0) > S_ANGLE_2:", math.fabs(r0) * 180 / math.pi) 
        return False
    elif math.fabs(r0) < S_ANGLE_1:
        if d2 > R_MAX_2 or d2 < R_MIM_2:
            print("d2 > R_MAX_2 or d2 < R_MIM_2:", d2) 
            return False
    else:
        if d2 < R_MIM_2:
            print("d2 < R_MIM_2", math.sqrt(d2)) 
            return False
        else:
            if r0 > 0:
                if ver[0] < ver[1] * k + b:
                    print("ver[0] < ver[1] * k + b", ver[0], ver[1] * k + b, k, b) 
                    return False
            else:
                if ver[0] < ver[1] * (-k) + b:
                    print("ver[0] < ver[1] * -k + b", ver[0], ver[1] * (-k) + b, k , b) 
                    return False
    return True

def move_to(v, speed=5000):
    c.mdi("g1 x" + "%f" % (v[0]) + " y" + "%f" % (v[1]) + " z"+ "%f" % (v[2]) + " f" + str(speed))
    print("g1 x" + str(v[0]) + " y" + str(v[1]) + " z"+ str(v[2]) + " f" + str(speed))
    c.wait_complete()
    return True

def is_almost_equal(v, tolerance=5):
    for i in v:
        error = math.fabs(i[0] - i[1])
        if (error > tolerance):
            return False
    return True

def position_get(isPoll=True):
    estop_set(1)  # estop off
    if (isPoll):
        s.poll()
    return [s.position[0:3], s.joint_actual_position[0:3]]


def co_calc(v, sin, cos, p, D=25, isComfirm=None):
    if isComfirm is None:
        x=p[0][0] + D*cos + (v[0] ) *cos - (v[1] ) * sin
        y=p[0][1] + D*sin + (v[1] )* cos +  (v[0] ) * sin
    else:
        x=p[0][0]  + (v[0] ) *cos - (v[1] ) * sin
        y=p[0][1]  + (v[1] )* cos +  (v[0] ) * sin
        
    return [x,y]

def get_machine_coordenates(vs, p=None):
    if p==None:
        p=position_get();
    cos = math.cos(p[1][0] * math.pi / 180)
    sin = math.sin(p[1][0] * math.pi / 180) 
    return [co_calc(v,sin,cos, p) for v in vs]

def get_machine_coordenate(v, p=None, isComfirm=None):
    if p==None:
        p=position_get();
    cos = math.cos(p[1][0] * math.pi / 180)
    sin = math.sin(p[1][0] * math.pi / 180)
    return co_calc(v, sin, cos, p, isComfirm=isComfirm)

de_top=220
de_speed=5000
de_pos={0:("g0",230,0,de_top, 10000), 
       1:("g16", -10, de_speed),
       2:("g16", 10, de_speed),
       3:("g16", 0, de_speed),
       }
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
    machine_list = []
    for i in range(len(de_pos) - 1):
        detection_move()
        co_list = get_coordenates(); 
        print("co_list", co_list)
        if (len(co_list)):
            p = position_get();
            machine_list += get_machine_coordenates(co_list, p)
    if len(machine_list):        
        print("machine_list", machine_list)
        scan_list_t = [map_to_grid(n) for n in machine_list]
        scan_list_t.sort()
        c=None
        for l in scan_list_t:
            if not c == l:
                c = l
                scan_list.append(c)
        print("scan_list", scan_list)
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
    print("scan_pos", scan_pos)
    move_to(scan_grid[scan_pos]) 
    cor = get_coordenate(scan_pos)
    print("cor", cor) 
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
            print("down_pos ", down_pos)
            uarm_state=Uarm_states.DOWN
    print("x, y", x, y)

def action_confirm():
    global uarm_state
    global confirm_pos
    global down_pos
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

try_num = 0
def action_down():
    global uarm_state
    global try_num
    move_to([down_pos[0][0], down_pos[0][1], pump_top])
    p_top = pump_top
    for i in range(10):
        if not h["s_pump"]:
            p_top = p_top-1
            move_to([down_pos[0][0], down_pos[0][1],p_top],speed=1000)
        else:
            uarm_state=Uarm_states.PUMP
            return
    if try_num == 1: 
        black_list_add(down_pos[1], down_pos[2])
        uarm_state=Uarm_states.SCAN
        try_num = 0;
    else:
        uarm_state=Uarm_states.DOWN
        try_num = 1

def action_pump():
    global uarm_state
    h['pump'] = 0
    time.sleep(1)
    uarm_state=Uarm_states.REMOVE


dump_pos=[[250, -200, pump_top],[200, -200, pump_top],[150, -200, pump_top] ]
dump_pos_index=0
dump_top = 140
def action_remove():
    global uarm_state
    global dump_pos_index
    
    v=[down_pos[0][0],down_pos[0][1],dump_top]
    move_to(v)
    v=[dump_pos[dump_pos_index][0],dump_pos[dump_pos_index][1],dump_top]
    move_to(v)
    move_to(dump_pos[dump_pos_index])
    h['pump']=1
    time.sleep(1.5)
    dump_pos_index += 1
    if dump_pos_index >= len(dump_pos):
        dump_pos_index=0
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

while(running):
    if h['s_switch']:
        uarm_state = Uarm_states.START
    print("uarm_state:", uarm_state)
    states_switch[uarm_state]()


