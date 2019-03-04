#!/usr/bin/env python
import socket as sk
Host="10.5.5.1"
Port=12346
s=sk.socket(sk.AF_INET, sk.SOCK_STREAM)
s.bind((Host, Port))
s.listen(1)
while(True):
    conn, addr = s.accept()
    print("Connnected by: ", addr)
    while True:
        data = conn.recv(64)
        if not data:
            print("------>")
            break;
        print(data)

