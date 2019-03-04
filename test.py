#!/usr/bin/env python
import select, socket, sys
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setblocking(0)
server.bind(('10.5.5.1', 12346))
server.listen(5)
inputs = [server]
outputs = []
message_queues = {}
tun=0
data_s = ""
data = ""
find_head=0

while inputs:
    readable, writable, exceptional = select.select(
        inputs, outputs, inputs)
    for s in readable:
        if s is server:
            connection, client_address = s.accept()
            connection.setblocking(0)
            inputs.append(connection)    
            print("------------------> new ", len(inputs),connection)
        else:
            data += s.recv(32)
            print("-->***********************************--<")
            if data:
                if find_head == 0:
                    index_h = data.find("S")
                    if index_h >= 0:
                        find_head=1
                        print("-->find head")
                        data = data[index_h:]
                if find_head == 1:
                    index_e = data.find("E")
                    if index_e >= 0:
                        print("-->find End")
                        find_head = 0
                        print(data[:index_e])
                        data = data[index_e:]
                if s not in outputs:
                    outputs.append(s)
            else:
                if s in outputs:
                    outputs.remove(s)
                inputs.remove(s)
                s.close()

    for s in writable:
        try:
            pass
        except Queue.Empty:
            outputs.remove(s)
        else:
            pass
            #            s.send(next_msg)

    for s in exceptional:
        print("------------------> remove ",connection)
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()
