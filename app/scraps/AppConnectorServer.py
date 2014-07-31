
# example: run AppConnectorServer Time

import sys; argv = getattr( sys, 'argv', [] )[ 1: ]

import socket

UDP_IP = "10.0.0.1"
UDP_PORT = 20320
UDP_TIMEOUT_SEC = 0.2

sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
sock.bind( ( UDP_IP, UDP_PORT ) )
sock.settimeout( UDP_TIMEOUT_SEC )

d = {}
try:
	while True:
		try: data, addr = sock.recvfrom( 1024 ) # buffer size is 1024 bytes
		except socket.timeout: continue
		data = data.strip()
		if not len( data ): continue
		key, val = data.split( ' ', 1 )
		match = [ int( pattern in key ) for pattern in argv ] # only take notice if argv is empty, or one of the argv args is a substring of the key
		if len( match ) and max( match ) == 0: continue 
		if d.get( key, None ) != val: print data  # only print if something has changed
		d[ key ] = val
except KeyboardInterrupt:
	sock.close()
