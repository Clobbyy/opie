#!/usr/bin/env python3
"""
Tiny OSC/UDP sniffer for SAFE loopback testing — prints every OSC message it
receives so you can confirm exactly what the relay would send to Eos *before*
pointing it at a real console.

Usage:
    opie-sniff            # listens on 0.0.0.0:8000
    opie-sniff 9000       # listens on a different port

Test flow:
    1. In the GUI (or config) set "NOMAD_IP": "127.0.0.1", "EOS_RX_PORT": 8000
    2. Terminal A:  opie-sniff 8000
    3. Terminal B:  opie
    4. Terminal C:  curl -s -X POST http://127.0.0.1:8765/command \
                        -H "X-Token: YOUR_TOKEN" --data "channel 5 at full"
    -> the sniffer prints:  /eos/chan/5/full
"""

import socket
import sys

from . import osclib


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    print(f"OSC sniffer listening on UDP 0.0.0.0:{port}  (Ctrl-C to stop)")
    try:
        while True:
            data, addr = sock.recvfrom(65535)
            try:
                address, args = osclib.decode(data)
                if address is None:
                    print(f"from {addr[0]}: (bundle, {len(data)} bytes)")
                else:
                    print(f"from {addr[0]}: {osclib.format_message(address, args)}")
            except Exception as e:  # never crash the sniffer on a weird packet
                print(f"from {addr[0]}: undecodable ({len(data)} bytes) {e}")
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
