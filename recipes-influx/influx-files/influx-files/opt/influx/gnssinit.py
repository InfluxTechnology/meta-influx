#!/usr/bin/env python3

import serial
ser =  serial.Serial("/dev/ttymxc2",baudrate=115200,timeout=1.0)
ser.write(b'AT+QGPSCFG="outport","uartdebug"\r');ser.read(1000)
ser.write(b'AT+QGPS=1\r');ser.read(1000)
