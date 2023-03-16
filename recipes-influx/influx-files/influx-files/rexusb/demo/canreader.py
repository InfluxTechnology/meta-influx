# SPDX-License-Identifier: GPL-2.0

#! /usr/bin/python

import os
import re

delimiters = " ", "(", ")", "[", "]"
regexPattern = '|'.join(map(re.escape, delimiters))

while True:
	with open('/var/run/rexgen/can0/rx', 'r') as pse:
		for line in pse:
			words = list(filter(None, re.split(r"[()\[\]\s]\s*", line)))
			
			timestamp = float(words[0])
			channel = int(words[1][3])
			ident = int(words[2], base=16)
			dlc = int(words[3])
			data = "";
			for i in range(dlc):
				data = data+words[4+i]

			print("Timestamp: ", timestamp, ", Channel: ", channel, ", Ident: ", ident, ", DLC: ", dlc, ", Data: ", data)
