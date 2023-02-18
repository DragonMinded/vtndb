import argparse
import os
import sys
from typing import List, Optional

from wiki import Wiki, Page
from terminal import Terminal


class Action:
    pass


class NavigateAction(Action):
    def __init__(self, uri: str) -> None:
        self.uri = uri


class BackAction(Action):
    pass


class SettingAction(Action):
    def __init__(self, setting: str, value: Optional[str]) -> None:
        self.setting = setting
        self.value = value


class Navigation:
    def __init__(self, wiki: Wiki) -> None:
        self.wiki = wiki
        self.stack: List[str] = []

    def navigate(self, uri: str) -> Page:
        self.stack.append(uri)
        return self.wiki.getPage(uri)

    def canGoBack(self) -> bool:
        return len(self.stack) > 1

    def back(self) -> Page:
        if not self.canGoBack():
            raise Exception("Nothing to go back to!")

        self.stack = self.stack[:-1]
        return self.wiki.getPage(self.stack[-1])


class Rendering:
    def __init__(self, terminal: Terminal) -> None:
        self.terminal = terminal
        self.input = ""
        self.page: Optional[Page] = None

    def displayPage(self, page: Page) -> None:
        self.page = page

        data = page.data
        if data.startswith("css"):
            data = data[3:]

        self.terminal.sendCommand(Terminal.CLEAR_SCREEN)
        self.terminal.sendCommand(Terminal.MOVE_CURSOR_ORIGIN)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.sendCommand(Terminal.SET_BOLD)
        self.terminal.sendText(f"{page.domain.root}:{page.path} -- {page.name}\n\n")
        self.terminal.sendCommand(Terminal.SET_NORMAL)

        while data:
            if "[" in data:
                before, data = data.split("[", 1)
                if "]" in data:
                    after, data = data.split("]", 1)

                    self.terminal.sendText(before)
                    self.terminal.sendCommand(Terminal.SET_BOLD)
                    self.terminal.sendText("[")
                    self.terminal.sendText(after)
                    self.terminal.sendText("]")
                    self.terminal.sendCommand(Terminal.SET_NORMAL)
                else:
                    self.terminal.sendText(before)
                    self.terminal.sendText("[")
            else:
                self.terminal.sendText(data)
                data = ""

        # Render status bar at the bottom.
        self.clearInput()

    def clearInput(self) -> None:
        self.terminal.moveCursor(self.terminal.rows, 1)
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_REVERSE)
        self.terminal.sendText(" " * self.terminal.columns)
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

        # Clear command.
        self.input = ""

    def displayError(self, error: str) -> None:
        # TODO: Display this on the VT-100
        print(error)

    def processInput(self, inputVal: bytes) -> Optional[Action]:
        if self.page is None:
            return None
        page = self.page

        if inputVal == Terminal.LEFT:
            row, col = self.terminal.fetchCursor()
            if col > 1:
                col -= 1
                self.terminal.moveCursor(row, col)
        elif inputVal == Terminal.RIGHT:
            row, col = self.terminal.fetchCursor()
            if col < (len(self.input) + 1):
                col += 1
                self.terminal.moveCursor(row, col)
        elif inputVal == Terminal.UP:
            raise Exception("Not implemented!")
        elif inputVal == Terminal.DOWN:
            raise Exception("Not implemented!")
        elif inputVal == Terminal.BACKSPACE:
            if self.input:
                # Just subtract from input.
                row, col = self.terminal.fetchCursor()

                if col == len(self.input) + 1:
                    self.input = self.input[:-1]

                    col -= 1
                    self.terminal.moveCursor(row, col)
                    self.terminal.sendCommand(Terminal.SET_REVERSE)
                    self.terminal.sendText(" ")
                    self.terminal.moveCursor(row, col)
                else:
                    raise Exception("Not implemented!")
        elif inputVal == b"\r":
            # Ignore this.
            pass
        elif inputVal == b"\n":
            # Execute command.
            if self.input[0] == "!":
                # Link navigation.
                try:
                    link = int(self.input[1:])
                    link -= 1

                    if link < 0 or link >= len(page.links):
                        self.displayError("Unknown link navigation request!")

                    if ":" in page.links[link] or not page.links[link].startswith("/"):
                        # Fully qualified path.
                        return NavigateAction(page.links[link])
                    else:
                        # Assume current domain.
                        return NavigateAction(f"{page.domain.root}:{page.links[link]}")
                except ValueError:
                    self.displayError("Invalid link navigation request!")
            elif self.input == "back":
                return BackAction()
            elif self.input.startswith("goto"):
                if " " not in self.input:
                    self.displayError("No page requested!")
                else:
                    _, newpage = self.input.split(" ", 1)
                    newpage = newpage.strip()

                    if ":" in newpage or not newpage.startswith("/"):
                        # Fully qualified path.
                        return NavigateAction(newpage)
                    else:
                        # Assume current domain.
                        return NavigateAction(f"{page.domain.root}:{newpage}")
            elif self.input.startswith("set"):
                if " " not in self.input:
                    self.displayError("No setting requested!")
                else:
                    _, setting = self.input.split(" ", 1)
                    setting = setting.strip()

                    if "=" in setting:
                        setting, value = setting.split("=", 1)
                        setting = setting.strip()
                        value = value.strip()
                    else:
                        setting = setting.strip()
                        value = None

                    return SettingAction(setting, value)
            elif self.input.startswith("cd"):
                if " " not in self.input:
                    self.displayError("No directory specified!")
                else:
                    _, newdir = self.input.split(" ", 1)
                    newdir = newdir.strip()

                    newpage = os.path.abspath(os.path.join(page.path, newdir))
                    if not newpage:
                        newpage = "/"

                    return NavigateAction(f"{page.domain.root}:{newpage}")
            else:
                self.displayError(f"Unrecognized command {self.input}")
        else:
            # Just add to input.
            row, col = self.terminal.fetchCursor()
            char = inputVal.decode("ascii")

            if col == len(self.input) + 1:
                self.input += char
                self.terminal.sendCommand(Terminal.SET_REVERSE)
                self.terminal.sendText(char)
            else:
                raise Exception("Not implemented!")

        # Nothing happening here!
        return None


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
            action = renderer.processInput(inputVal)
            if isinstance(action, NavigateAction):
                page = nav.navigate(action.uri)
                renderer.displayPage(page)
            elif isinstance(action, BackAction):
                if nav.canGoBack():
                    page = nav.back()
                    renderer.displayPage(page)
                else:
                    renderer.clearInput()
            elif isinstance(action, SettingAction):
                if action.setting in {"cols", "columns"}:
                    if action.value not in {"80", "132"}:
                        renderer.displayError(
                            f"Unrecognized column setting {action.value}"
                        )
                    elif action.value == "80":
                        if terminal.columns != 80:
                            terminal.set80Columns()
                            renderer.displayPage(page)
                        else:
                            renderer.clearInput()
                    elif action.value == "132":
                        if terminal.columns != 132:
                            terminal.set132Columns()
                            renderer.displayPage(page)
                        else:
                            renderer.clearInput()
                else:
                    renderer.displayError(f"Unrecognized setting {action.setting}")

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
