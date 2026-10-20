"""Read Pico's CDC diagnostics, without sending application commands.

macOS may require permission to configure the USB serial device. Opening CDC
with DTR enables Pico SDK stdout. Do not use 1200 baud (the SDK bootloader trigger).
This script does not reset, flash, change device clocks, or write SD/save files.
"""
import argparse
import array
import fcntl
import os
import select
import termios
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="Exact /dev/cu.usbmodem... port of this Pico")
    parser.add_argument("--seconds", type=int, default=20, choices=range(1, 61), metavar="1..60")
    args = parser.parse_args()
    if not args.port.startswith("/dev/cu.usbmodem") or "/" in args.port[len("/dev/"):]:
        parser.error("Pass the observed USB CDC port, not a regular file.")
    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    original = None
    try:
        original = termios.tcgetattr(fd)
        attrs = termios.tcgetattr(fd)
        attrs[0] = attrs[1] = attrs[3] = 0
        attrs[4] = attrs[5] = termios.B115200
        attrs[6][termios.VMIN] = attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        fcntl.ioctl(fd, termios.TIOCMBIS, array.array("i", [termios.TIOCM_DTR | termios.TIOCM_RTS]))
        until = time.monotonic() + args.seconds
        count = 0
        while True:
            remaining = until - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([fd], [], [], min(1, remaining))
            if ready:
                data = os.read(fd, 8192)
                if data:
                    print(data.decode("utf-8", "replace"), end="", flush=True)
                    count += len(data)
        print("\nSERIAL_CAPTURE_BYTES", count)
    finally:
        try:
            if original is not None:
                termios.tcsetattr(fd, termios.TCSANOW, original)
        finally:
            os.close(fd)


if __name__ == "__main__":
    main()
