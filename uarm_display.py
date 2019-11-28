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
import errno

sock_log = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock_log.connect(("10.193.20.62", 6000))
except:
    pass
def print_log(log):
    try:
        sock_log.send(log + '\n')
        
    except:
        pass

edgescle_ip="192.168.0.1"
#edgescle_ip="10.193.20.33"
edgescle_port=8280
print_log("log test\n")
wifi_client = 0
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

heartbeat_id = 0

h = hal.component("IO")
h.newpin("pump", hal.HAL_BIT, hal.HAL_OUT)
h.newpin("s_switch", hal.HAL_BIT, hal.HAL_IN)
h.newpin("s_pump", hal.HAL_BIT, hal.HAL_IN)
h.newpin("rt_power", hal.HAL_BIT, hal.HAL_OUT)
h.newpin("rt_reset", hal.HAL_BIT, hal.HAL_OUT)
h.ready()

h["pump"] = 1
h["rt_power"] = 1
h["rt_reset"] = 0

def rt_reset():
    h["rt_reset"] = 1
    time.sleep(0.5)
    h["rt_reset"] = 0


def get_wifi_status():
    global wifi_lost_num
    try:
        wifi_client.send('\x5a\x5a\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00')   # send heartbeat to rt
    except:
        pass
    if (wifi_lost_num > 2):
        return "1"
    else:
        wifi_lost_num += 1
        return "0"

class timer_call(object):
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
                self.start()

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

header = [0x55, 0xAA, 0x5A, 0x5A]
header_str= '\x55\xaa\x5a\x5a'
version = [0x00, 0x01]
version_str = '\x00\x01'

devid_str = "i.MX_led_id0"
mydevid = bytearray(list(devid_str) + ['\x00'] * (64 - len(devid_str)))
type_reg = [0x00, 0x01]
type_reg_reply = "\x00\x02"
type_unreg = [0x00, 0x03]
type_unreg_reply = "\x00\x04"
type_set = "\x00\x05"
type_set_reply =  [0x00, 0x06]
type_get = "\x00\x07"
type_get_reply =   [0x00, 0x08]
type_ota =  "\x00\x09"
type_ota_reply = [0x00, 0x0A]
type_event = [0x00, 0x0B]
color=0
color_str=["Red", "Green", "Yellow", "Blue"]
color_str_l=["red", "green", "yellow", "blue"]

ota_server_port = 8089
ota_header_str='\x5A\x5A'
ota_package_size = 2048

OTA_GET_VERSION	= 0x01
OTA_UPDATE_REQ	= 0x02
OTA_UPDATE_START = 0x03
OTA_UPDATE_CONTINUE	= 0x04
OTA_UPDATE_RETRANS	= 0x05
OTA_UPDATE_DATA		= 0x06
OTA_UPDATE_FINISH	= 0x07
OTA_START_LOG		= 0x08
OTA_ENTER_CONSOLE	= 0x09
OTA_CMD_ERASE		= 0x0A
OTA_CMD_UPDATE		= 0x0B
OTA_CMD_ROLLBACK	= 0x0C
OTA_CMD_ERASE_OK	= 0x0D
OTA_CMD_ERASE_ERR	= 0x0E
OTA_CMD_REBOOT      = 0x0F

class ota(object):
    def __init__(self, port):
        self.ota_port = port
        self.timer = timer_call(1, self.run)
        self.ota_status = 0
        self.ota_recv = ""
        self.ota_cmd = 0
        self.ota_version = 0
        self.ota_firmware = []
        self.ota_firmware_name = ""
        self.ota_firmware_index = 0
        self.ota_index = 0
        self.version = 0
        self.firmware_name = ""
        self.find_header = 0
        self.ota_sk = -1
        self.ota_ck = -1
        h["rt_power"] = 0

    def ota_cmd_erase(self):
        self.ota_cmd = 1
        print_log("get_ota_cmd_erase")

    def ota_cmd_update(self):
        self.ota_cmd = 0
        print_log("get_ota_cmd_update")

    def ota_cmd_force(self):
        self.ota_cmd = 2
        print_log("get_ota_cmd_force")

    def ota_set_firmware(self, image, file_version, name=""):
        self.ota_firmware = image
        print_log(file_version)
        try:
            self.ota_version = int(file_version)
        except:
            pass
        self.ota_firmware_name = name
        print_log("set_newfiemware: %s - %s" % (self.ota_firmware_name, file_version))

    def short_to_list_little(self, i):  # little endian
        ret = []
        ret.append(i & 0xff)
        ret.append((i >> 8) & 0xff)
        return ret

    def int_to_list_little(self, i):  # little endian
        ret = []
        ret.append(i & 0xff)
        ret.append((i >> 8) & 0xff)
        ret.append((i >> 16) & 0xff)
        ret.append((i >> 24) & 0xff)
        return ret

    def list_to_short_little(self, l):  # little endian
        return (ord(l[1]) << 8) + ord(l[0])

    def ota_calc_checksum(self, val):
        l = len(val) / 2
        val_int16 = [(ord(val[i + 1]) << 8) + ord(val[i]) for i in range(0, len(val), 2)]
        sum = 0
        for i in val_int16:
            sum += i
        return self.short_to_list_little(sum)
    def ota_disruption(self):
        self.timer.stop()
        try:
            self.ota_ck.close()
        except:
            pass
        try:
            self.ota_sk.close()
        except:
            pass
        print_log("ota_disruption..")
    
    def ota_rt_restart(self):
        print_log("ota_rt_restart")
        rt_reset()
        try:
            self.ota_ck.send('\x5a\x5a\x00\x00\x0F\x00\x00\x00\x00\x00\x00\x00')
            print_log("wifi_clinet send reset to bootload")
        except:
            print_log("wifi_client send reset failed to bootload")
            pass
        

        try:
            print_log( wifi_client)
            wifi_client.send('\x5a\x5a\x00\x00\x0F\x00\x00\x00\x00\x00\x00\x00')
            print_log("wifi_client send reset to OpenMV")
        except:
            print_log("wifi_client send reset failed to OpenMV")
            pass

    def ota_update(self):
        self.ota_ck.setblocking(True)
        self.ota_ck.settimeout(5.0)
        self.ota_firmware_index = 0
        self.ota_index = 1
        self.ota_recv = ""
        packet_size = 0
        flash_erase_timeout = 6   # waiting rt erase flash 30 seconds, or reboot rt chip..
        print_log("ota_update start...")

        if self.ota_status ==  5:   # send a update request to rt
            self.ota_ck.send('\x5a\x5a' + bytearray(self.short_to_list_little(self.ota_version))
                     + '\x02\x00\x00\x00\x05\x00\x00\x00' + bytearray(self.int_to_list_little(len(self.ota_firmware))))
        print_log("\tota_update send the update request")
        if self.ota_status >= 5 :
            find_header = 0
            while True:
                try:
                    recv = self.ota_ck.recv(64)
                    if recv == "":  # tcp connection is disconnected
                        self.ota_ck.close()
                        self.ota_status = 1  # re-waiting for rt to connect
                        return

                    self.ota_recv += recv
                    if not find_header:
                        index = self.ota_recv.find(ota_header_str)
                        if index < 0:
                            self.ota_recv = ""
                        else:
                            self.ota_recv = self.ota_recv[index:]  # make sure the self.recv begin with Frame_header
                            find_header = 1

                    recv_len = len(self.ota_recv)
                    if recv_len < 12:
                        continue

                    if ord(self.ota_recv[4]) == OTA_UPDATE_CONTINUE and self.ota_status >= 6 :
                        self.ota_index += packet_size
                        self.ota_firmware_index += 1
                        self.ota_status = 7

                    if ord(self.ota_recv[4]) == OTA_UPDATE_START:
                        self.ota_index = 0
                        self.ota_firmware_index = 0
                        self.ota_status = 6
                        print_log("\tota_update starts..")

                    if ord(self.ota_recv[4]) == OTA_UPDATE_RETRANS:
                        self.ota_status += 1
                        print_log("\tota_update retrans: index: %s try_times: %s." % (self.ota_index, self.ota_status - 7))
                        if  self.ota_status - 7 > 10: # the time of re-transmit > 10.  reboot RT
                            self.ota_ck.send('\x5a\x5a\x00\x00\x0F\x00\x00\x00\x00\x00\x00\x00')
                            print_log("\tota_update retrans failed, will reboot RT chip..")
                            break

                    if ord(self.ota_recv[4]) == OTA_UPDATE_FINISH:
                        print_log("\tota_update is finished")
                        break

                    if len(self.ota_firmware) - self.ota_index > ota_package_size :
                        packet_size = ota_package_size
                    else :
                        packet_size = len(self.ota_firmware) - self.ota_index

                    check_sum = self.ota_calc_checksum(self.ota_firmware[self.ota_index: self.ota_index + packet_size])
                    self.ota_ck.send('\x5a\x5a' + bytearray(self.short_to_list_little(self.ota_firmware_index))
                                        + '\x06\x00\x00\x00' + bytearray(self.short_to_list_little(packet_size))
                                        + bytearray(check_sum)
                                        + bytearray(self.ota_firmware[self.ota_index: self.ota_index + packet_size] + '\x00' * (ota_package_size - packet_size)))
                    self.ota_recv = ""
                except socket.error as msg:
                    if msg.message == 'timed out' and self.ota_status == 5: 
                        if flash_erase_timeout > 0:
                            flash_erase_timeout -= 1
                        else:
                            self.ota_ck.send('\x5a\x5a\x00\x00\x0F\x00\x00\x00\x00\x00\x00\x00')
                            print_log("\tota_update erase flash timeout, will reboot RT chip..")
                            break
                    else:
                        break
            self.ota_ck.close()
            self.ota_status = 1  # re-waiting for rt to connect

    def run(self):
        if self.ota_status == 0:   #  ota tcp service is ready
            try:
                self.ota_sk= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.ota_sk.bind(("0.0.0.0", self.ota_port))
                self.ota_sk.setblocking(False)
                self.ota_sk.listen(2)
                self.ota_status = 1
                print_log("ota_: start listen %d" % self.ota_port)
            except socket.error as msg:
                self.timer.delay(5)
                self.ota_sk.close()
                print_log("ota_: %s and retry after 5s" % msg.strerror)
        if self.ota_status >= 1:         # waiting for rt to connect
            try:
                ota_ck, _ = self.ota_sk.accept()  # if new connection come before the last connection disconnected, close the old connection.
                print_log("ota : new connection ..")
                try:
                    self.ota_ck.close()
                except:
                    pass
                self.ota_ck = ota_ck
                self.ota_ck.setblocking(False)
                self.ota_status = 2
            except socket.error as msg:
                if msg.errno != errno.EAGAIN:
                    self.ota_sk.close()
                    self.ota_status = 0
                else:
                    pass

        if self.ota_status > 4:  # Rt has no firmware and it is ready to update
            if self.ota_version != 0 and len(self.ota_firmware) != 0:
                self.ota_update()
            else:
                print_log("ota : frimware is not ready")
                return

        if self.ota_status > 1:    # the tcp connection has been established

            try:
                recv = self.ota_ck.recv(64)
                if recv == "":      # tcp connection is disconnected
                    self.ota_ck.close()
                    self.ota_status = 1  # re-waiting for rt to connect
                    print_log("ota : tcp client is disconected")
                    return

                self.ota_recv += recv
                while True:
                    if not self.find_header:
                        index = self.ota_recv.find(ota_header_str)
                        if index < 0:
                            self.recv = ""
                            return
                        self.ota_recv = self.ota_recv[index:]  # make sure the self.recv begin with Frame_header
                        self.find_header = 1

                    recv_len = len(self.ota_recv)
                    if recv_len < 12:
                        return

                    if ord(self.ota_recv[4]) ==  OTA_START_LOG:
                        print_log("ota : Recv OTA_START_LOG")
                        self.ota_status = 2         #  rt is online
                        if self.ota_cmd == 1:       # send erase cmd after rt is online
                            print_log("ota : Send OTA_CMD_ERASE")
                            self.ota_ck.send('\x5a\x5a\x00\x00\x0a\x00\x00\x00\x00\x00\x00\x00')
                            self.ota_status = 3     # waiting for rt to reply.
                        else:     # send get_version cmd
                            print_log("ota : Send OTA_GET_VERSION")
                            self.ota_ck.send('\x5a\x5a\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00')
                            self.ota_status = 4

                    if ord(self.ota_recv[4]) == OTA_CMD_ERASE_OK or ord(self.ota_recv[4]) == OTA_CMD_ERASE_ERR:
                            # reboot the rt
                            if ord(self.ota_recv[4]) == OTA_CMD_ERASE_OK:
                                print_log("ota : recv OTA_CMD_ERASE_OK")
                            else:
                                print_log("ota : recv OTA_CMD_ERASE_ERR")
                            self.ota_cmd = 0        #
                            self.ota_status = 1
                            self.ota_ck.send('\x5a\x5a\x00\x00\x0F\x00\x00\x00\x00\x00\x00\x00')
                            self.ota_ck.close()
                            self.ota_status = 1

                    if ord(self.ota_recv[4]) ==  OTA_GET_VERSION:
                        print_log("ota : recv OTA_GET_VERSION")
                        if self.ota_status != 4:
                            self.ota_ck.send('\x5a\x5a\x00\x00\x0F\x00\x00\x00\x00\x00\x00\x00')
                            self.ota_ck.close()
                            self.ota_status = 1
                            print_log("ota : recv OTA_GET_VERSION with status != 4, reboot rt..")
                        else:
                            dat_len = self.list_to_short_little(self.ota_recv[8:10])
                            if recv_len < 12 + dat_len:
                                return
                            self.version = self.list_to_short_little(self.ota_recv[2:4])
                            self.firmware_name = self.ota_recv[12:dat_len + 12]
                               # has got the rt version information
                            print_log("ota : rt version = %d ota_version = %d" % (self.version, self.ota_version))
                            if self.ota_cmd == 2 or self.version == 0 or self.ota_version > self.version:
                                self.ota_status = 5
                                self.ota_cmd = 0

                            else:
                                print_log("ota OTA_UPDATE_FINISH")
                                self.ota_status = 1  # tell rt to go ahead
                                self.ota_ck.send('\x5a\x5a\x00\x00\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
                                self.ota_ck.close()
                    self.find_header = 0
                    self.ota_recv = self.ota_recv[12:]
            except socket.error as msg:
                if msg.errno != errno.EAGAIN:  # reboot RT
                    try:
                        self.ota_ck.send('\x5a\x5a\x00\x00\x0F\x00\x00\x00\x00\x00\x00\x00')
                        self.ota_ck.close()
                    except:
                        pass
                    self.ota_status = 1


class edgescale(object):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.status = 0
        self.timer = timer_call(1, self.run)
        self.recv = ''
        self.find_header = 0
	self.ota = ota(ota_server_port)
			
    def version_check(self, v):
        if v == version_str:
            return True
        return False

    def devid_check(self, devid):
        if devid == mydevid:
            return True
        return False

    def reg_reply_check(self, res):
        if res[0:2] == 'ok':
            return True
        return False

    def set_attr(self, attr):
        print_log("set_attr ")
        print_log(attr[0:5])
        print_log("set_value ")
        print_log(attr[68:74])
        if (attr[0:5] == 'color'):
            global  color
            if attr[68:71] == 'red' or attr[68:71] == 'Red':
                color = 0
            elif attr[68:73] == 'green' or attr[68:73] == 'Green':
                color = 1
            elif attr[68:74] == 'yellow' or attr[68:74] == 'Yellow':
                color = 2
            elif attr[68:72] == 'blue' or attr[68:72] == 'blue':
                color = 3
            else:
                pass
        if (attr[0:6] == 'reboot'):
            self.ota.ota_rt_restart()

    def get_attr(self, attr):
        print_log("get_attr ")
        print_log(attr[0:5])
        if (attr[0:5] == 'color'):
            print_log(color_str_l[color]);
            color_value = color_str_l[color] + '\x00' * (64 - len(color_str_l[color]))
            color_arr = "color" + '\x00' * (64 - len("color"))
            color_res = bytearray(header + version + type_get_reply + [0]*4 + self.struct_data(mydevid + color_arr +"ok"+ '\x00'*6 + "\x00\x00\x00\x04" + color_value))
            self.sock.send(color_res)
        else:
            print_log("successed");
            res_value = "\x00" + '\x00' * (64 - 1)
            res = bytearray(header + version + type_get_reply + [0]*4 + self.struct_data(mydevid + attr[0:64] +"ok"+ '\x00'*6 + "\x00\x00\x00\x01" + res_value))
            self.sock.send(res)

    def int_to_list(self, i):
        ret = []
        ret.append((i >> 24) & 0xff)
        ret.append((i >> 16) & 0xff)
        ret.append((i >> 8) & 0xff)
        ret.append(i & 0xff)
        return ret

    def str_to_int(self, s):
        i  = ord(s[0]) << 24
        i += ord(s[1]) << 16
        i += ord(s[2]) << 8
        i += ord(s[3])
        return i

    def calc_xorsum(self, l):
        mask = 31
        val = 0
        for i in l:
            if isinstance(i, str):
                i = ord(i)
            val ^= i << (i & mask)
        return self.int_to_list(val)

    def struct_data(self, dat):
        if isinstance(dat, str) or isinstance(dat, bytearray):
            dat = list(dat)
        l = len(dat)
        ret = self.int_to_list(l)
        ret = ret + dat
        ret = self.calc_xorsum(ret[4:]) + ret
        return ret

    def update_firmware(self, fm):
        filename = fm[0:fm[0:64].find('\x00')]
        file_type = fm[64:64 + fm[64:72].find('\x00')]
        file_version = fm[72:72 + fm[72:80].find('\x00')]
        check_type = fm[80:80 + fm[80:88].find('\x00')]
        check_code = fm[88:152]
        print(file_version)
        if filename == "null.bin":
            self.ota.ota_cmd_erase()
        else:
	    self.ota.ota_set_firmware(fm[152:], file_version, filename)
	self.ota.ota_rt_restart()

    #
    def disruption(self):
        self.timer.stop()
        self.sock.close()
        self.ota.ota_disruption()

    def run(self):
        print("self->status = %d", self.status)
        if self.status == 0:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.ip, self.port))
                self.sock.setblocking(False)
                self.status = 1
            except socket.error as msg:
                if msg.errno == errno.EINPROGRESS:
                    self.timer.delay(10)
                elif msg.errno == errno.ECONNREFUSED:
                    self.timer.delay(10)
                else:
                    self.timer.stop()
                self.sock.close()
                return

        if self.status == 1:
            devid = list(devid_str) + [0] * (64 - len(devid_str))
            try:
                self.sock.send(bytearray(header + version + type_reg +[0,0,0,0]+ self.struct_data(devid)))
                self.status = 2
            except  socket.error as msg:
                if msg.errno != errno.EPIPE:
                    self.timer.stop()
                self.sock.close()
                self.status = 0
                return

        if self.status > 1:
            try:
                re = self.sock.recv(1024)
                if re == "":                   #tcp connection has been disconnected
                    self.sock.close()
                    self.status = 0
                    return

                self.recv += re
                while True:
                    if not self.find_header:
                        index = self.recv.find(header_str)
                        if index < 0:
                            self.recv = ""
                            return
                        self.recv = self.recv[index:]   #self.recv will begin with Frame_header
                        self.find_header = 1

                    recv_len = len(self.recv)
                    if recv_len < 20:
                        return
                    
                    dat_len = self.str_to_int(self.recv[16:20])
                    
                    if self.recv[6:8] == type_ota:
                        while recv_len <  dat_len + 20:
                            recv = self.sock.recv(1024)
                            if recv == "":                   #tcp connection has been disconnected
                                self.sock.close()
                                self.status = 0
                                return
                            self.recv += recv
                            recv_len = len(self.recv)
                    
                    if recv_len <  dat_len + 20:
                        return                # tool short, do not have a complete frame.  continue to receive

                    xorsum = [ord(i) for i in self.recv[12:16]]
                    if self.version_check(self.recv[4:6]) and xorsum == self.calc_xorsum(self.recv[20:20+dat_len]) and self.devid_check(self.recv[20:84]):
                            if self.recv[6:8] == type_reg_reply:
                                if self.reg_reply_check(self.recv[84:92]):
                                    self.status = 11
                                else:
                                    self.status = 1   #register is failed, return status 1 to re-register
                            elif self.recv[6:8] == type_set:
                                self.set_attr(self.recv[84:216])
                            elif self.recv[6:8] == type_get:
                                self.get_attr(self.recv[84:152])
                            elif self.recv[6:8] == type_ota:
                                print_log("get ota_image");
                                self.update_firmware(self.recv[84:dat_len + 20])
                                self.sock.send(bytearray(header + version + type_ota_reply +[0,0,0,0]+ self.struct_data(mydevid + self.ota.ota_firmware_name + '\x00' * (64 - len(self.ota.ota_firmware_name)) + "ok" + '\x00'*10)))
                            else:
                                pass
                    remain = recv_len - dat_len - 20
                    if remain == 0:
                        self.recv = ""
                        self.find_header = 0
                        return
                    else:
                        self.find_header = 0
                        self.recv =  self.recv[dat_len + 20:]
            except socket.error as msg:
                 if msg.errno == errno.EAGAIN:    #Receive no data
                    if self.status > 1 and self.status < 10:
                        self.status += 1
                    elif self.status == 10:
                        self.statu = 1   # Register request reply timeout. re-send the register request.
                 else :
                    self.sock.close()
                    self.timer.stop()
#Receive the blocks coordinates sending from OpenMV.
#Receive the set of the color we want to catch.
#Receive the thread over command.

def receive_coordinate (datq, sev, gev,pipe_r):
    global running
    global color
    global wifi_lost_num
    global wifi_client
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setblocking(0)
        server.bind((Host, Port))
    except:
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
                        print("recevice pthread exit..")
                        exit(0)
            else:
                try:
                    data = s.recv(24)
                except:
                    inputs.remove(s)
                    s.close()

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
                        wifi_client = s
                        wifi_lost_num = 0
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
    time.sleep(0.5) 
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

edge = edgescale(edgescle_ip, edgescle_port)
os.system("halcmd source ./postgui.hal")
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
opc_ua_triger = 0
camera_adjust_step = 0
def key_is_up():
    if h['s_switch'] == 0:
        return True
# if opc_ua_triger == 1, skip the camera adjustment steps
def action_start():
    global uarm_state
    global switch_test
    global camera_adjust_step
    global opc_ua_triger
    print_log("camera_adjust_step = %d" % camera_adjust_step)
    if opc_ua_triger == 0 and camera_adjust_step != 2:
        if camera_adjust_step == 0:
            if key_is_up():
                camera_adjust_step = 1
        elif camera_adjust_step == 1:
            if not key_is_up():
                camera_adjust_step = 2

        time.sleep(0.5)
        return

    if camera_adjust_step != 3: 
        estop_set(1)  # estop off
        machine_set(1)
        task_mode_set(linuxcnc.MODE_MANUAL)
        unhome_joints(joints)
        switch_test = "1"
        for i in range(0,8):
            c.home(i)
        cnc_util.wait_for_home(joints, timeout=20)
        task_mode_set(linuxcnc.MODE_MDI)
        move_to([250, 0, 140])
    
    if camera_adjust_step == 2:
        camera_adjust_step = 3
        time.sleep(0.5)
        v = get_coordenate()
        if len(v):
            print("test: ", get_machine_coordenate(v))
        if key_is_up():
            camera_adjust_step = 0
        else:
            return
    opc_ua_triger = 0
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
        edge.ota.ota_rt_restart()
        return "ok"
    elif (args[0] == 'color'):
        return UARM_s.set_color(args[1])
    elif (args[0] == 'ota_erase'):
        edge.ota.ota_cmd_erase()
        edge.ota.ota_rt_restart()
        return "ok"
    elif (args[0] == 'ota_force_update') or args[0] == 'ota_update':
        if args[0] == 'ota_force_update':
            edge.ota.ota_cmd_force()
        with open('./image/version.log', 'r') as f:
            ver = f.readline()[:-1]
            name = f.readline()[:-1]
        with open('./image/%s' % name, 'rb') as f:
            dat = f.read()
        edge.ota.ota_set_firmware(dat, ver, name)
        edge.ota.ota_rt_restart()
        return "ok"


    else:
        return "none"

def UARM_cmd_get(args):
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
        global opc_ua_triger
        opc_ua_triger = s
    
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
    edge.disruption()

signal.signal(signal.SIGINT, signal_exit_handler)
server.start()
while(running):
    if h['s_switch']:
        uarm_state = Uarm_states.START
    states_switch[uarm_state]()
print("exit...")
server.stop()

