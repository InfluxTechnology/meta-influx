#!/usr/bin/env python2.7

import serial
ser =  serial.Serial("/dev/ttymxc2",baudrate=115200,timeout=1.0)
ser.write("AT+UGPS=0\r\n");ser.read(1000)
ser.write("AT+USIO=4\r\n");ser.read(1000)
ser.write("AT+UGPRF=1\r\n");ser.read(1000)
ser.write("AT+UGIND=1\r\n");ser.read(1000)
ser.write("AT+UGPS=1,0,3\r\n");ser.read(1000)
ser.write("AT+UGRMC=1\r\n");ser.read(1000)
ser.write("AT+UGGGA=1\r\n");ser.read(1000)
