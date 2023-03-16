#  SPDX-License-Identifier: GPL-2.0
#! /usr/bin/python

import os
import re
import time

while True:
	with open('/var/run/rexgen/can0/rx', 'a') as f:
		timestamp = 12345
		channel = 0
		ident = 298
		dlc = 5

		data = [12, 13, 14, 15, 16]
		
		line = "(" + '{}'.format(timestamp) + ") can" + '{}'.format(channel) + " " + '{:x}'.format(ident) + " [" + '{}'.format(dlc) + "]"

		for i in range(dlc):
				line = line + " " + '{:02x}'.format(data[i])

		f.write(line + "\n");
		time.sleep(1);

