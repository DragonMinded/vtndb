import serial  # type: ignore
import time
from typing import Optional


class Terminal:
    ESCAPE: bytes = b"\x1B"

    REQUEST_STATUS: bytes = b"[5n"
    STATUS_OKAY: bytes = b"[0n"

    MOVE_CURSOR_ORIGIN: bytes = b"[H"
    CLEAR_SCREEN: bytes = b"[2J"

    UP: bytes = b"[A"
    DOWN: bytes = b"[B"
    LEFT: bytes = b"[D"
    RIGHT: bytes = b"[C"
    BACKSPACE: bytes = b"\x7F"

    def __init__(self, port: str, baud: int) -> None:
        self.serial = serial.Serial(port, baud, timeout=0.01)
        self.pending = b""

        # First, connect and figure out what's going on.
        self.sendCommand(self.REQUEST_STATUS)
        if self.recvResponse() != self.STATUS_OKAY:
            raise Exception("Terminal is not okay!")

        # Reset terminal.
        self.sendCommand(self.CLEAR_SCREEN)
        self.sendCommand(self.MOVE_CURSOR_ORIGIN)

    def sendCommand(self, cmd: bytes) -> None:
        self.serial.write(self.ESCAPE)
        self.serial.write(cmd)

    def sendText(self, text: str) -> None:
        self.serial.write(text.encode("ascii"))

    def recvResponse(self, timeout: Optional[float] = None) -> bytes:
        gotResponse: bool = False
        accum: bytes = b""

        start = time.time()
        while True:
            val = self.serial.read()
            if not val:
                if gotResponse or (timeout and (time.time() - start) > timeout):
                    # Got a full command here.
                    while accum and (accum[0:1] != self.ESCAPE):
                        self.pending += accum[0:1]
                        accum = accum[1:]

                    if accum and accum[0:1] == self.ESCAPE:
                        return accum[1:]
                    else:
                        accum = b""
                        if timeout:
                            return b""
                        else:
                            gotResponse = False

                continue

            gotResponse = True
            accum += val

    def recvInput(self) -> Optional[bytes]:
        # TODO: Possibly parse any command responses we got here.
        escaped = self.recvResponse(timeout=0.01)
        if escaped:
            if escaped in {self.UP, self.DOWN, self.LEFT, self.RIGHT}:
                return escaped
            else:
                raise Exception("Unhandled response " + str(escaped))

        val: Optional[bytes] = None
        if self.pending:
            val = self.pending[0:1]
            self.pending = self.pending[1:]
        return val
