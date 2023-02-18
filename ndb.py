import argparse
import sys
from typing import List

from wiki import Wiki, Page
from terminal import Terminal


class Navigation:
    def __init__(self, wiki: Wiki) -> None:
        self.wiki = wiki
        self.stack: List[str] = []

    def navigate(self, uri: str) -> Page:
        self.stack.append(uri)
        return self.wiki.getPage(uri)

    def canGoBack(self) -> bool:
        return bool(self.stack)

    def back(self) -> Page:
        if not self.canGoBack():
            raise Exception("Nothing to go back to!")

        uri = self.stack[-1]
        self.stack = self.stack[:-1]
        return self.wiki.getPage(uri)


class Rendering:
    def __init__(self, terminal: Terminal) -> None:
        self.terminal = terminal

    def displayPage(self, page: Page) -> None:
        data = page.data
        if data.startswith("css"):
            data = data[3:]

        self.terminal.sendCommand(Terminal.CLEAR_SCREEN)
        self.terminal.sendCommand(Terminal.MOVE_CURSOR_ORIGIN)
        self.terminal.sendText(f"{page.domain.root}:{page.path} -- {page.name}\n\n")
        self.terminal.sendText(data)


def main(port: str, baudrate: int) -> int:
    wiki = Wiki("https://samhayzen.github.io/ndb-web/web.json")
    nav = Navigation(wiki)
    page = nav.navigate("NX.INDEX")

    terminal = Terminal(port, baudrate)
    renderer = Rendering(terminal)
    renderer.displayPage(page)

    while True:
        inputVal = terminal.recvInput()
        if inputVal:
            print(inputVal)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VT-100 terminal driver for NDBWiki")

    parser.add_argument(
        "--port",
        default="/dev/ttyUSB0",
        type=str,
        help="Serial port to open, defaults to /dev/ttyUSB0",
    )
    parser.add_argument(
        "--baud",
        default=9600,
        type=int,
        help="Baud rate to use with VT-100, defaults to 9600",
    )
    args = parser.parse_args()

    sys.exit(main(args.port, args.baud))
