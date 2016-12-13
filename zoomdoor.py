#!/usr/bin/env python

import threading
import socket
import smbus
import time

# -----------------------------------------------
# init i2c
#
# Input : Port 0x20 Option 0x12
# 1. Door Open Switch	---- ---L
# 2. Door Close Switch	---- --L-
# 3. Door Locker
# 	3.1 Normal			---- HL--
#	3.2 30 Degree		---- HH--
#	3.3 Lock			---- LLLH
# 4. PER Switch			---L ----
# 5. Key Switch 		--L- ----
#
# Output : Port 0x27 Option 0x14
# 1. Motor Door Close	---- --LH
# 2. Motor Door Open	---- --HL
# 3. Interior Lamp		---- -H--
# -----------------------------------------------
bus = smbus.SMBus(1)
port_in = 0x20
port_out = 0x27
ch1_set = 0x00
ch2_set = 0x01
ch1_in = 0x12
ch2_in = 0x13
ch1_out = 0x14
ch2_out = 0x15
set_input = 0xff
set_output = 0x00
cmd = 0x00
is_door_locked = False
is_disabled = False

# -----------------------------------------------
# init socket
# -----------------------------------------------
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def init_i2c():
	bus.write_byte_data(port_in, ch1_set, set_input)
	bus.write_byte_data(port_in, ch2_set, set_input)
	bus.write_byte_data(port_out, ch1_set, set_output)
	bus.write_byte_data(port_out, ch2_set, set_output)

def open_door():
	global cmd
	cmd = cmd & 0b11111100 	# set bit 1,2 = 0
	cmd = cmd | 0b00000010
	bus.write_byte_data(port_out, ch1_out, cmd)
	
	while True:
		if bus.read_byte_data(port_in, ch1_in) & 0b00000001 == 0b00000000:
			cmd = cmd & 0b11111100
			bus.write_byte_data(port_out, ch1_out, cmd)
			break

def close_door():
	global cmd
	cmd = cmd & 0b11111100	# set bit 1,2 = 0
	cmd = cmd | 0b00000001
	bus.write_byte_data(port_out, ch1_out, cmd)

	while True:
		if bus.read_byte_data(port_in, ch1_in) & 0b00000010 == 0b00000000:
			cmd = cmd & 0b11111100
			bus.write_byte_data(port_out, ch1_out, cmd)
			break

def open_lamp():
	global cmd
	cmd = cmd | 0b00000100
	bus.write_byte_data(port_out, ch1_out, cmd)
	
def close_lamp():
	global cmd
	cmd = cmd & 0b11111011
	bus.write_byte_data(port_out, ch1_out, cmd)

def thread_network():
	s.connect(('192.168.1.10', 2510))
	s.send('SESSIONID=ZOOMDOOR\n');
	threading.Thread(target=thread_socket_recv).start()
	threading.Thread(target=thread_socket_send).start()

def thread_socket_send():
	global is_door_locked
	global is_disabled
	msg_door = ''
	msg_key = ''
	msg_per = ''
	msg_disable = ''
	msg_lock = ''
	msg = ''

	while True:
		status = bus.read_byte_data(port_in, ch1_in)

		#--------------------------------------------
		if status & 0b00000001 == 0b00000000:
			msg = 'F001 D0\n'

		elif status & 0b00000010 == 0b00000000:
			msg = 'F001 D1\n'

		else:
			msg = 'F001 D2\n'

		if msg != msg_door:
			s.send(msg)
			msg_door = msg

		#--------------------------------------------
		if status & 0b00010000 == 0b00000000:
			msg = 'F003 D1\n'
			if not is_disabled:
				open_lamp()
		else:
			msg = 'F003 D0\n'

		if msg != msg_per:
			s.send(msg)
			msg_per = msg

		#--------------------------------------------
		if status & 0b00100000 == 0b00000000:
			msg = 'F004 D1\n'
			close_lamp()
			is_disabled = True
		else:
			msg = 'F004 D0\n'
			is_disabled = False

		if msg != msg_key:
			s.send(msg)
			msg_key = msg

		#--------------------------------------------
		if status & 0b00000100 == 0b00000100:
			msg = 'F005 D1\n'
		else:
			msg = 'F005 D0\n'

		if msg != msg_disable:
			s.send(msg)
			msg_disable= msg

		#--------------------------------------------
		if status & 0b00001000 == 0b00000000:
			msg = 'F006 D1\n'
			is_door_locked = True
		else:
			msg = 'F006 D0\n'
			is_door_locked = False

		if msg != msg_lock:
			s.send(msg)
			msg_lock = msg

		time.sleep(0.1)

def thread_socket_recv():
	try:
		while True:
			data = s.recv(64)
			data = data.upper()
			data = data.rstrip()
			dev_id = data.split(' ')[0]
			dev_cmd = data.split(' ')[1]

			if not is_door_locked: 		# check the door was locked
				if dev_id == 'F001':
					if dev_cmd == 'S1':
						close_door()
					elif dev_cmd == 'S0':
						open_door()
				
				elif dev_id == 'F002':
					if dev_cmd == 'S1':
						open_lamp()
					elif dev_cmd == 'S0':
						close_lamp()

	except ValueError:
		print 'data error <' + data + '>'

def main():
	init_i2c()
	threading.Thread(target=thread_network).start()

if __name__ == '__main__':
	main()
