import serial  # type: ignore
import time
from typing import Optional, Tuple


class Terminal:
    ESCAPE: bytes = b"\x1B"

    REQUEST_STATUS: bytes = b"[5n"
    STATUS_OKAY: bytes = b"[0n"

    REQUEST_CURSOR: bytes = b"[6n"

    MOVE_CURSOR_ORIGIN: bytes = b"[H"
    CLEAR_SCREEN: bytes = b"[2J"

    SET_132_COLUMNS: bytes = b"[?3h"
    SET_80_COLUMNS: bytes = b"[?3l"

    SET_BOLD: bytes = b"[1m"
    SET_NORMAL: bytes = b"[m"
    SET_REVERSE: bytes = b"[7m"

    SAVE_CURSOR: bytes = b"7"
    RESTORE_CURSOR: bytes = b"8"

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
        self.sendCommand(self.SET_80_COLUMNS)
        self.sendCommand(self.SET_NORMAL)
        self.columns: int = 80
        self.rows: int = 24

    def set132Columns(self) -> None:
        self.sendCommand(self.SET_132_COLUMNS)
        self.columns = 132

    def set80Columns(self) -> None:
        self.sendCommand(self.SET_80_COLUMNS)
        self.columns = 80

    def sendCommand(self, cmd: bytes) -> None:
        self.serial.write(self.ESCAPE)
        self.serial.write(cmd)

    def moveCursor(self, row: int, col: int) -> None:
        self.sendCommand(f"[{row};{col}H".encode("ascii"))

    def fetchCursor(self) -> Tuple[int, int]:
        self.sendCommand(self.REQUEST_CURSOR)
        resp = self.recvResponse()
        if resp[:1] != b"[" or resp[-1:] != b"R":
            raise Exception("Invalid response for cursor fetch!")
        respstr = resp[1:-1].decode("ascii")
        row, col = respstr.split(";", 1)
        return int(row), int(col)

    def sendText(self, text: str) -> None:
        def fb(data: str) -> bytes:
            try:
                return data.encode("ascii")
            except UnicodeEncodeError:
                return b"+"

        self.serial.write(b"".join(fb(s) for s in text))

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
                        # We could have some regular input after this. So parse the command a little.
                        accum = accum[1:]

                        for offs in range(len(accum)):
                            val = accum[offs : (offs + 1)]
                            if val not in {
                                b"0",
                                b"1",
                                b"2",
                                b"3",
                                b"4",
                                b"5",
                                b"6",
                                b"7",
                                b"8",
                                b"9",
                                b";",
                                b"?",
                                b"[",
                            }:
                                # This is the last character.
                                if accum[offs + 1 :]:
                                    self.pending += accum[offs + 1 :]
                                return accum[: (offs + 1)]

                        raise Exception("Should have found end of command marker!")
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
