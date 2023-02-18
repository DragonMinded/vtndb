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


class HomeAction(Action):
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


class RendererCore:
    def __init__(self, terminal: Terminal, rows: int) -> None:
        self.terminal = terminal
        self.rows = rows

    def scrollUp(self) -> None:
        pass

    def scrollDown(self) -> None:
        pass


class TextRendererCore(RendererCore):
    def __init__(self, terminal: Terminal, rows: int) -> None:
        super().__init__(terminal, rows)
        self.text: List[str] = []
        self.line: int = 0

    def wordWrap(self, text: str) -> str:
        # Make things easier to deal with.
        text = text.replace("\r\n", "\n")

        newText: str = ""
        curLine: str = ""

        def joinLines() -> None:
            nonlocal newText
            nonlocal curLine

            if not curLine:
                return

            if not newText:
                newText = curLine
                curLine = ""
            else:
                if newText[-1] == "\n":
                    newText = newText + curLine
                    curLine = ""
                else:
                    newText = newText + "\n" + curLine
                    curLine = ""

        def spaceLeft() -> int:
            nonlocal curLine

            return self.terminal.columns - len(curLine)

        while text:
            if len(text) <= spaceLeft():
                # Just append the end.
                curLine += text
                text = ""
            else:
                # First, if there's a newline somewhere, see if it falls within this line.
                # if so, then just add everything up to and including it and move on.
                newlinePos = text.find("\n")
                if newlinePos >= 0:
                    chunkLen = newlinePos + 1

                    # We intentionally allow the newline to trail off because we don't auto-wrap,
                    # so it's okay to "print" it at the end since the next word will be on the
                    # new line anyway.
                    if chunkLen <= (spaceLeft() + 1):
                        curLine += text[:chunkLen]
                        text = text[chunkLen:]
                        joinLines()
                        continue

                # If we get here, our closest newline is on the next line somewhere (or beyond), or
                # does not exist. So we need to find the first space character to determine that
                # word's length.
                spacePos = text.find(" ")
                nextIsSpace = True
                if spacePos < 0:
                    # If we don't find a space, treat the entire rest of the text as a single word.
                    spacePos = len(text)
                    nextIsSpace = False

                if spacePos < spaceLeft():
                    # We have enough room to add the word AND the space.
                    if nextIsSpace:
                        curLine += text[: (spacePos + 1)]
                        text = text[(spacePos + 1) :]
                    else:
                        curLine += text[:spacePos]
                        text = text[spacePos:]
                elif spacePos == spaceLeft():
                    # We have enough room for the word but not the space, so add a newline instead.
                    if nextIsSpace:
                        curLine += text[:spacePos] + "\n"
                        text = text[(spacePos + 1) :]
                    else:
                        curLine += text[:spacePos]
                        text = text[spacePos:]
                else:
                    # We can't fit this, leave it for the next line if possible. However, if the
                    # current line is empty, that means this word is longer than wrappable. In
                    # that case, split it with a newline at the wrap point.
                    if curLine:
                        joinLines()
                    else:
                        width = spaceLeft()
                        curLine += text[:width]
                        text = text[width:]
                        joinLines()

        # Join the final line.
        joinLines()
        return newText

    def displayText(self, text: str) -> None:
        # First, we need to wordwrap the text based on the terminal's width.
        text = self.wordWrap(text)
        self.text = text.split("\n")

        # Control our scroll region, only erase the text we want.
        # TODO: Calculate this based on self.rows and such.
        self.terminal.moveCursor(3, 1)
        self.terminal.setScrollRegion(3, self.terminal.rows - 2)

        # Display the visible chunk of text.
        self.line = 0
        self._displayText(self.line, self.rows)

        # No longer need scroll region protection.
        self.terminal.clearScrollRegion()

    def scrollUp(self) -> None:
        if self.line > 0:
            self.line -= 1

            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.moveCursor(3, 1)
            self.terminal.setScrollRegion(3, self.terminal.rows - 2)
            self.terminal.sendCommand(Terminal.MOVE_CURSOR_UP)
            self._displayText(self.line, self.line + 1)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def scrollDown(self) -> None:
        if self.line < (len(self.text) - self.rows):
            self.line += 1

            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.setScrollRegion(3, self.terminal.rows - 2)
            self.terminal.moveCursor(self.terminal.rows - 2, 1)
            self.terminal.sendCommand(Terminal.MOVE_CURSOR_DOWN)
            self._displayText(self.line + (self.rows - 1), self.line + self.rows)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def _displayText(self, startVisible: int, endVisible: int) -> None:
        line = 0
        linkDepth = 0
        lastLine = min(self.rows + self.line, len(self.text), endVisible)
        while line < lastLine:
            # Grab the text itself, add a newline if we aren't the last line (don't want to scroll).
            text = self.text[line]
            if line != lastLine - 1:
                text = text + "\n"
            line += 1

            while text:
                openLinkPos = text.find("[")
                closeLinkPos = text.find("]")

                if openLinkPos < 0 and closeLinkPos < 0:
                    # No links in this line.
                    if line > startVisible:
                        self.terminal.sendText(text)
                    text = ""
                elif openLinkPos >= 0 and closeLinkPos < 0:
                    # Started a link in this line, but didn't end it.
                    linkDepth += 1
                    before, text = text.split("[", 1)

                    if line > startVisible:
                        self.terminal.sendText(before)
                    if linkDepth == 1:
                        # Only bold on the outermost link marker.
                        self.terminal.sendCommand(Terminal.SET_BOLD)
                    if line > startVisible:
                        self.terminal.sendText("[")
                elif (openLinkPos < 0 and closeLinkPos >= 0) or (
                    closeLinkPos < openLinkPos
                ):
                    # Finished a link on in this line, but there's no second start or
                    # the second start comes later.
                    after, text = text.split("]", 1)

                    if line > startVisible:
                        self.terminal.sendText(after)
                        self.terminal.sendText("]")
                    if linkDepth == 1:
                        self.terminal.sendCommand(Terminal.SET_NORMAL)

                    linkDepth -= 1
                else:
                    # There's an open and close on this line. Simply highlight it as-is. No need
                    # to handle incrementing/decrementing the depth.
                    before, text = text.split("[", 1)

                    if line > startVisible:
                        self.terminal.sendText(before)
                    if linkDepth == 0:
                        # Only bold on the outermost link marker.
                        self.terminal.sendCommand(Terminal.SET_BOLD)
                    if line > startVisible:
                        self.terminal.sendText("[")

                    after, text = text.split("]", 1)

                    if line > startVisible:
                        self.terminal.sendText(after)
                        self.terminal.sendText("]")
                    if linkDepth == 0:
                        self.terminal.sendCommand(Terminal.SET_NORMAL)


class Renderer:
    def __init__(self, terminal: Terminal) -> None:
        self.terminal = terminal
        self.input = ""
        self.page: Optional[Page] = None
        self.lastError = ""
        self.renderer = RendererCore(terminal, 20)

    def displayPage(self, page: Page) -> None:
        # Remember the page for going back to it for navigation.
        self.page = page

        # Render status bar at the bottom.
        self.clearInput()

        # First, wipe the screen and display the title.
        self.terminal.moveCursor(self.terminal.rows - 2, 1)
        self.terminal.sendCommand(Terminal.CLEAR_LINE)
        self.terminal.sendCommand(Terminal.CLEAR_TO_ORIGIN)
        self.terminal.sendCommand(Terminal.MOVE_CURSOR_ORIGIN)

        # Reset text display and put title up.
        self.terminal.setAutoWrap()
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.sendCommand(Terminal.SET_BOLD)
        self.terminal.sendText(f"{page.domain.root}:{page.path} -- {page.name}")
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.clearAutoWrap()

        # Render out the text of the page.
        if page.data.startswith("css"):
            self.renderer = TextRendererCore(self.terminal, 20)
            self.renderer.displayText(page.data[3:])

        # Move cursor to where we expect it for input.
        self.terminal.moveCursor(self.terminal.rows, 1)

    def clearInput(self) -> None:
        # Clear error display.
        self.displayError("")

        self.terminal.moveCursor(self.terminal.rows, 1)
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_REVERSE)
        self.terminal.sendText(" " * self.terminal.columns)
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

        # Clear command.
        self.input = ""

    def displayError(self, error: str) -> None:
        if error == self.lastError:
            return

        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.moveCursor(self.terminal.rows - 1, 1)
        self.terminal.sendCommand(Terminal.CLEAR_LINE)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.sendCommand(Terminal.SET_BOLD)
        self.terminal.sendText(error)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)
        self.lastError = error

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
            self.renderer.scrollUp()
        elif inputVal == Terminal.DOWN:
            self.renderer.scrollDown()
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
                    elif ":" in page.links[link] or not page.links[link].startswith(
                        "/"
                    ):
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
            elif self.input == "home":
                return HomeAction()
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
    renderer = Renderer(terminal)
    renderer.displayPage(page)

    while True:
        inputVal = terminal.recvInput()
        if inputVal:
            action = renderer.processInput(inputVal)
            if isinstance(action, NavigateAction):
                page = nav.navigate(action.uri)
                renderer.displayPage(page)
            elif isinstance(action, HomeAction):
                page = nav.navigate("NX.INDEX")
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
