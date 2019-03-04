#!/usr/bin/env python

import os
import posixpath
import BaseHTTPServer
import urllib
import cgi
import shutil
import mimetypes
import re

__all__ = ["SimpleHTTPRequestHandler"]
__author__ = "wxy"

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from SimpleHTTPServer import SimpleHTTPRequestHandler
import BaseHTTPServer

igh_proc_file_path = '/proc/ethercat/igh_ec_performance_log'

save_file_flag = 0

try:
    save_file = open('save_performance', 'r')
    save_file_flag = 1
except IOError:
    save_file_flag = 0
    print "save_file is not accessible."

def get_save_file_info():
    if (save_file_flag == 0):
        return '0\t0\t0'
    buf = save_file.readline()
    buf = buf.strip('\n')
    offset = save_file.tell()

    tmp_buf = save_file.readline()
    if not tmp_buf:
        save_file.seek(0)
    else:
        save_file.seek(offset)
    return buf;

class CORSRequestHandler (SimpleHTTPRequestHandler):
    def end_headers (self):
        self.send_header('Access-Control-Allow-Origin', '*')
        SimpleHTTPRequestHandler.end_headers(self)
		
    def do_GET (self):
        """Serve a GET request."""
        save_buf = get_save_file_info()
        try:
            proc_file =open(igh_proc_file_path, 'r')
            proc_buf = proc_file.readline()
            proc_buf = proc_buf.strip('\n')
            proc_file.close()
        except IOError:
            proc_buf = '0\t0\t0'
            print "proc_file is not accessible."
        buf = proc_buf + '\t' + save_buf
        self.protocal_version = 'HTTP/1.1'
        self.send_response(200)  
        self.send_header("Welcome", "Contect")         
        self.end_headers()  
        self.wfile.write(buf)
    def do_POST(self):
        """Serve a POST request."""
        self.protocal_version = 'HTTP/1.1'
        self.send_response(200)
        self.send_header("Welcome", "Contect")         
        self.end_headers()
        datas=self.rfile.read(int(self.headers['content-length']))
        print datas
 
 

if __name__ == '__main__':
    BaseHTTPServer.test(CORSRequestHandler, BaseHTTPServer.HTTPServer)
