import argparse
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

from wiki import Wiki, Domain, Page
from terminal import Terminal


class Action:
    pass


class NullAction(Action):
    pass


class NavigateAction(Action):
    def __init__(self, uri: str) -> None:
        self.uri = uri


class BackAction(Action):
    pass


class HomeAction(Action):
    pass


class HelpAction(Action):
    pass


class RandomAction(Action):
    pass


class ExitAction(Action):
    pass


class SettingAction(Action):
    def __init__(self, setting: str, value: Optional[str]) -> None:
        self.setting = setting
        self.value = value


class NavigationException(Exception):
    pass


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
            raise NavigationException(
                "Nothing to go back to, check canGoBack before calling this!"
            )

        self.stack = self.stack[:-1]
        return self.wiki.getPage(self.stack[-1])


class RendererCore:
    def __init__(self, terminal: Terminal, top: int, bottom: int) -> None:
        self.terminal = terminal
        self.top = top
        self.bottom = bottom
        self.rows = (bottom - top) + 1

    def scrollUp(self) -> None:
        pass

    def scrollDown(self) -> None:
        pass

    def pageUp(self) -> None:
        pass

    def pageDown(self) -> None:
        pass

    def goToTop(self) -> None:
        pass

    def goToBottom(self) -> None:
        pass

    def processInput(self, inputStr: str) -> Optional[Action]:
        return None


class TextRendererCore(RendererCore):
    def __init__(self, terminal: Terminal, top: int, bottom: int) -> None:
        super().__init__(terminal, top, bottom)
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

    def displayText(self, text: str, forceRefresh: bool = False) -> None:
        # First, we need to wordwrap the text based on the terminal's width.
        text = self.wordWrap(text)
        self.text = text.split("\n")

        # Control our scroll region, only erase the text we want.
        self.terminal.moveCursor(self.top, 1)
        self.terminal.setScrollRegion(self.top, self.bottom)

        # Display the visible chunk of text. For an initial draw, we're good
        # relying on our parent renderer to have cleared the viewport.
        self.line = 0
        self._displayText(self.line, self.line + self.rows, forceRefresh)

        # No longer need scroll region protection.
        self.terminal.clearScrollRegion()

    def scrollUp(self) -> None:
        if self.line > 0:
            self.line -= 1

            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self.terminal.sendCommand(Terminal.MOVE_CURSOR_UP)
            self._displayText(self.line, self.line + 1, False)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def scrollDown(self) -> None:
        if self.line < (len(self.text) - self.rows):
            self.line += 1

            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self.terminal.moveCursor(self.bottom, 1)
            self.terminal.sendCommand(Terminal.MOVE_CURSOR_DOWN)
            self._displayText(self.line + (self.rows - 1), self.line + self.rows, False)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def pageUp(self) -> None:
        line = self.line - (self.rows - 1)
        if line < 0:
            line = 0

        if line != self.line:
            self.line = line

            # Gotta redraw the whole thing.
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self._displayText(self.line, self.line + self.rows, True)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def pageDown(self) -> None:
        line = self.line + (self.rows - 1)
        if line > (len(self.text) - self.rows):
            line = len(self.text) - self.rows

        if line != self.line:
            self.line = line

            # Gotta redraw the whole thing.
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self._displayText(self.line, self.line + self.rows, True)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def goToTop(self) -> None:
        line = 0
        if line != self.line:
            self.line = line

            # Gotta redraw the whole thing.
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self._displayText(self.line, self.line + self.rows, True)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def goToBottom(self) -> None:
        line = len(self.text) - self.rows
        if line != self.line:
            self.line = line

            # Gotta redraw the whole thing.
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self._displayText(self.line, self.line + self.rows, True)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def _displayText(
        self, startVisible: int, endVisible: int, wipeNonText: bool
    ) -> None:
        bolded = False
        boldRequested = False

        def sendText(text: str) -> None:
            nonlocal bolded
            nonlocal boldRequested

            if bolded != boldRequested:
                bolded = boldRequested
                if bolded:
                    self.terminal.sendCommand(Terminal.SET_BOLD)
                else:
                    self.terminal.sendCommand(Terminal.SET_NORMAL)

            self.terminal.sendText(text)

        def setBold(bold: bool) -> None:
            nonlocal boldRequested
            boldRequested = bold

        displayed = 0
        line = 0
        linkDepth = 0
        lastLine = min(self.rows + self.line, len(self.text), endVisible)
        while line < lastLine:
            # Grab the text itself, add a newline if we aren't the last line (don't want to scroll).
            text = self.text[line]
            needsClear = wipeNonText and (len(text) < self.terminal.columns)
            line += 1

            while text:
                openLinkPos = text.find("[")
                closeLinkPos = text.find("]")

                if openLinkPos < 0 and closeLinkPos < 0:
                    # No links in this line.
                    if line > startVisible:
                        sendText(text)
                    text = ""
                elif openLinkPos >= 0 and closeLinkPos < 0:
                    # Started a link in this line, but didn't end it.
                    linkDepth += 1
                    before, text = text.split("[", 1)

                    if line > startVisible:
                        sendText(before)
                    if linkDepth == 1:
                        # Only bold on the outermost link marker.
                        setBold(True)
                    if line > startVisible:
                        sendText("[")
                elif (openLinkPos < 0 and closeLinkPos >= 0) or (
                    closeLinkPos < openLinkPos
                ):
                    # Finished a link on in this line, but there's no second start or
                    # the second start comes later.
                    after, text = text.split("]", 1)

                    if line > startVisible:
                        sendText(after)
                        sendText("]")
                    if linkDepth == 1:
                        setBold(False)

                    linkDepth -= 1
                else:
                    # There's an open and close on this line. Simply highlight it as-is. No need
                    # to handle incrementing/decrementing the depth.
                    before, text = text.split("[", 1)

                    if line > startVisible:
                        sendText(before)
                    if linkDepth == 0:
                        # Only bold on the outermost link marker.
                        setBold(True)
                    if line > startVisible:
                        sendText("[")

                    after, text = text.split("]", 1)

                    if line > startVisible:
                        sendText(after)
                        sendText("]")
                    if linkDepth == 0:
                        setBold(False)

            if line > startVisible:
                displayed += 1

                if needsClear:
                    self.terminal.sendCommand(Terminal.CLEAR_TO_END_OF_LINE)

                if line != endVisible:
                    self.terminal.sendText("\n")

        if wipeNonText:
            clearAmount = endVisible - startVisible
            while displayed < clearAmount:
                self.terminal.sendCommand(Terminal.CLEAR_LINE)

                if displayed < (self.rows - 1):
                    self.terminal.sendText("\n")

                displayed += 1


class SearchRendererCore(TextRendererCore):
    def __init__(
        self,
        domain: Domain,
        renderer: "Renderer",
        terminal: Terminal,
        top: int,
        bottom: int,
    ) -> None:
        super().__init__(terminal, top, bottom)
        self.domain = domain
        self.renderer = renderer
        self.displayedDomain = ""
        self.displayedRoot = ""
        self.displayedHelp = ""
        self.results: List[Page] = []

    def displaySearch(self, searchInput: str) -> None:
        lines = searchInput.split("\n")
        self.displayedDomain = lines[0]
        self.displayedRoot = lines[1]

        data = "\n".join(lines[2:])
        self.displayedHelp = "\n".join(data.split("css"))
        self.displayText(self.displayedHelp)

    def displayResults(self, term: str, results: List[Tuple[Page, int]]) -> None:
        processedResults: List[str] = []
        for i, result in enumerate(results):
            processedResults.append(f"[#{i + 1}] {result[1]} Hits - {result[0].name}")
            processedResults.append(result[0].path)

        self.line = 0
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.displayText(
            "\n".join(
                [
                    self.displayedHelp,
                    "",
                    f'Searching term "{term}" in {self.displayedRoot} of {self.displayedDomain}',
                    "",
                    f'Results for "{term}":' if results else f'No results for "{term}"',
                    *processedResults,
                ]
            ),
            forceRefresh=True,
        )
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)
        self.results = [r[0] for r in results]

    def processInput(self, inputStr: str) -> Optional[Action]:
        if inputStr == "search" or inputStr.startswith("search "):
            if " " not in inputStr:
                self.renderer.displayError("No search term specified!")
            else:
                _, searchTerm = inputStr.split(" ", 1)
                searchTerm = searchTerm.strip().lower()

                # Grab all of the articles and search them.
                pages: List[Tuple[Page, int]] = []
                for page in self.domain.getAllPages():
                    lowerData = page.data.lower()
                    if searchTerm in lowerData:
                        pages.append((page, len(lowerData.split(searchTerm)) - 1))

                self.renderer.clearInput()
                self.displayResults(searchTerm, pages)

            return NullAction()
        elif inputStr[0] == "#":
            # Result navigation.
            try:
                result = int(inputStr[1:])
                result -= 1

                if result < 0 or result >= len(self.results):
                    self.renderer.displayError("Unknown result navigation request!")
                else:
                    # Navigate to the page whole cloth.
                    page = self.results[result]
                    return NavigateAction(f"{page.domain.root}:{page.path}")
            except ValueError:
                self.renderer.displayError("Invalid result navigation request!")

            return NullAction()

        # Didn't handle this.
        return None


class DictionaryRendererCore(TextRendererCore):
    def __init__(
        self,
        renderer: "Renderer",
        terminal: Terminal,
        top: int,
        bottom: int,
    ) -> None:
        super().__init__(terminal, top, bottom)
        self.renderer = renderer
        self.instructions = [
            "Commands:",
            '    "roots" - See a list of this language\'s root words',
            '    "root [root word]" - look at the definition of a specific root word (Ex: "root ka")',
            '    "words" - See a list of this language\'s words',
            '    "word [word]" - look at the definition of a specific word (Ex: "word apple")',
        ]
        self.roots: List[Dict[str, Any]] = []
        self.words: List[Dict[str, Any]] = []
        self.sort = "alphabetical"

    def displayDictionary(self, searchInput: str) -> None:
        data = json.loads(searchInput)
        self.sort = str(data["defSortBy"])
        self.roots = list(data["roots"])
        self.words = list(data["words"])

        splash = "\n".join(
            [
                *self.instructions,
                "",
                f"[{data['langName']} Dictionary]",
                "",
                data["splashPageText"],
            ]
        )
        self.displayText(splash)

    def displayRoot(self, root: Dict[str, Any]) -> None:
        self.line = 0
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.displayText(
            "\n".join(
                [
                    *self.instructions,
                    "",
                    f'[ {root["name"]} ] -- ("{root["pronunciation"]}")',
                    f"Type: {root['type']}",
                    "",
                    "Meaning:",
                    f"   {root['meaning']}",
                    "",
                    f"Origin: {root.get('origin', 'undefined')}",
                    "",
                    "Words containing this root:",
                    *[f"   {word}" for word in root["examples"]],
                ]
            ),
            forceRefresh=True,
        )
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def displayRoots(self) -> None:
        roots: List[str] = []
        for root in self.roots:
            roots.append(f"  {root['name']} ({root['type']}) -- {root['meaning']}")

        self.line = 0
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.displayText(
            "\n".join(
                [
                    *self.instructions,
                    "",
                    *roots,
                ]
            ),
            forceRefresh=True,
        )
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def displayWord(self, word: Dict[str, Any]) -> None:
        self.line = 0
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.displayText(
            "\n".join(
                [
                    *self.instructions,
                    "",
                    f'[ {word["name"]} ] -- ("{word["pronunciation"]}")',
                    "",
                    "Meaning:",
                    f"   {word['definition']}",
                    "",
                    f"Breakdown: {word['breakdown']}",
                    "",
                    f"Origin: {word.get('origin', 'undefined')}",
                    "",
                    "Examples:",
                    f"   {word['example']}",
                    "",
                    "Roots:",
                    *[f"   {root}" for root in word["roots"]],
                ]
            ),
            forceRefresh=True,
        )
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def displayWords(self) -> None:
        words: List[str] = []
        for word in self.words:
            words.append(f"  [  {word['name']}  ]")
            words.append(f"    {word['definition']}")

        self.line = 0
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.displayText(
            "\n".join(
                [
                    *self.instructions,
                    "",
                    *words,
                ]
            ),
            forceRefresh=True,
        )
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def displayFailure(self, searchType: str, searchStr: str) -> None:
        self.line = 0
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.displayText(
            "\n".join(
                [
                    *self.instructions,
                    "",
                    f'Could not find {searchType} "{searchStr}"',
                    "Make sure you spelled it correctly, and try again.",
                ]
            ),
            forceRefresh=True,
        )
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def processInput(self, inputStr: str) -> Optional[Action]:
        if inputStr == "roots":
            self.renderer.clearInput()
            self.displayRoots()

            return NullAction()
        elif inputStr == "root" or inputStr.startswith("root "):
            if " " not in inputStr:
                self.renderer.displayError("No root specified!")
            else:
                _, root = inputStr.split(" ", 1)
                root = root.strip().lower()

                # Find this root.
                for data in self.roots:
                    if data["name"].lower() == root:
                        self.renderer.clearInput()
                        self.displayRoot(data)
                        break
                else:
                    self.displayFailure("root", root)

            return NullAction()
        elif inputStr == "words":
            self.renderer.clearInput()
            self.displayWords()

            return NullAction()
        elif inputStr == "word" or inputStr.startswith("word "):
            if " " not in inputStr:
                self.renderer.displayError("No word specified!")
            else:
                _, word = inputStr.split(" ", 1)
                word = word.strip().lower()

                # Find this word.
                for data in self.words:
                    if data["name"].lower() == word:
                        self.renderer.clearInput()
                        self.displayWord(data)
                        break
                else:
                    self.displayFailure("word", word)

            return NullAction()

        # Didn't handle this.
        return None


class CalendarRendererCore(TextRendererCore):
    def __init__(
        self,
        renderer: "Renderer",
        terminal: Terminal,
        top: int,
        bottom: int,
    ) -> None:
        super().__init__(terminal, top, bottom)
        self.renderer = renderer
        self.instructions = [
            "Commands:",
            '    "day [number]" - Select a specific day (ex: "day 23")',
            '    "month [number]" - Go to a specific month (ex: "month 2")',
            '    "year [number]" - Go to a specific year (ex: "year 107")',
        ]
        self.months = [
            "CopperFlame",
            "Crystone",
            "Deriz",
            "Bloom",
            "Lereai",
            "HarvestCrest",
            "Karmil",
            "SteelFell",
            "Lunakin",
            "SiltCrest",
            "TinBell",
            "Etherglide",
            "Crimson",
            "Apofel",
        ]
        self.suffix = {
            1: "st",
            2: "nd",
            3: "rd",
            21: "st",
            22: "nd",
            23: "rd",
            31: "st",
            32: "nd",
            33: "rd",
        }
        self.events: List[Dict[str, Any]] = []
        self.links: List[str] = []

        self.day = -1
        self.month = 1
        self.year = 1
        self.maxYear = 0
        self.minYear = 0

    def padDay(self, day: int, amount: int) -> str:
        dayval = str(day)
        while len(dayval) < amount:
            dayval = "0" + dayval
        return dayval

    def addSuffix(self, number: int) -> str:
        numval = str(number)
        return numval + self.suffix.get(number, "th")

    def formatNow(self) -> str:
        if self.day == -1:
            return f"{self.months[self.month - 1]}, Year {self.year} -- {self.month}/{self.year}"
        else:
            return f"{self.addSuffix(self.day)} of {self.months[self.month - 1]}, Year {self.year} -- {self.day}/{self.month}/{self.year}"

    def displayCalendar(self, searchInput: str) -> None:
        data = json.loads(searchInput)
        self.day = -1
        self.month = int(data["startMonth"])
        self.year = int(data["startYear"])
        self.minYear = int(data["minYear"])
        self.maxYear = int(data["maxYear"])

        for event in data["events"]:
            # This should be a day, month, year triple-list
            origin = tuple(event["origin"])

            if event["repeats"] == 0:
                self.events.append(
                    {
                        "date": origin,
                        "name": event["name"],
                        "link": event["link"],
                        "tags": event["tags"],
                    }
                )
            elif event["repeats"] > 0:
                # Should be a day, month, year repeat instruction.
                period = tuple(event["period"])

                for _ in range(event["repeats"]):
                    self.events.append(
                        {
                            "date": origin,
                            "name": event["name"],
                            "link": event["link"],
                            "tags": event["tags"],
                        }
                    )
                    origin = (
                        origin[0] + period[0],
                        origin[1] + period[1],
                        origin[2] + period[2],
                    )
            elif event["repeats"] < 0:
                # Should be a day, month, year repeat instruction.
                period = tuple(event["period"])

                while origin[2] <= self.maxYear:
                    self.events.append(
                        {
                            "date": origin,
                            "name": event["name"],
                            "link": event["link"],
                            "tags": event["tags"],
                        }
                    )
                    origin = (
                        origin[0] + period[0],
                        origin[1] + period[1],
                        origin[2] + period[2],
                    )

        self.displayToday(False)

    def hasEvent(self, day: int, month: int, year: int) -> bool:
        for event in self.events:
            if event["date"][0] != day:
                continue
            if event["date"][1] != month:
                continue
            if event["date"][2] != year:
                continue

            return True
        return False

    def getEvents(self, day: int, month: int, year: int) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for event in self.events:
            if event["date"][0] != day:
                continue
            if event["date"][1] != month:
                continue
            if event["date"][2] != year:
                continue

            events.append(event)
        return events

    def highlightDay(self, day: int) -> str:
        if day == self.day:
            return f"[{self.padDay(day, 2)}]"
        elif self.hasEvent(day, self.month, self.year):
            return f"-{self.padDay(day, 2)}-"
        else:
            return f" {self.padDay(day, 2)} "

    def eventLines(self) -> List[str]:
        if self.day == -1:
            return [
                "No day selected.",
                'Type "day [day number]" to select a day of the month.',
            ]
        else:
            events = self.getEvents(self.day, self.month, self.year)

            if events:
                self.links = []
                lines: List[str] = []

                for i, event in enumerate(events):
                    self.links.append(event["link"])
                    lines.append(f"[#{i + 1}] {event['name']}")
                    lines.append(event["link"])

                return lines
            else:
                return [
                    "No events for this day.",
                    'Type "day [day number]" to select a different day of the month.',
                ]

    def calendarLines(self) -> List[str]:
        lines = []
        for start in range(1, 40, 5):
            lines.append("".join(self.highlightDay(x) for x in range(start, start + 5)))

        return [
            "\u250c" + "\u2500" * 20 + "\u2510",
            *["\u2502" + line + "\u2502" for line in lines],
            "\u2514" + "\u2500" * 20 + "\u2518",
            "",
            *self.eventLines(),
        ]

    def displayToday(self, refresh: bool) -> None:
        splash = "\n".join(
            [
                *self.instructions,
                "",
                f"[{self.formatNow()}]",
                *self.calendarLines(),
            ]
        )

        if refresh:
            self.line = 0
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.displayText(splash, forceRefresh=refresh)
        if refresh:
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def processInput(self, inputStr: str) -> Optional[Action]:
        if inputStr == "day" or inputStr.startswith("day "):
            if " " not in inputStr:
                self.renderer.displayError("No day specified!")
            else:
                _, day = inputStr.split(" ", 1)
                day = day.strip().lower()

                try:
                    daynum = int(day)

                    if daynum < 1 or daynum > 40:
                        self.renderer.displayError("Invalid day specified!")
                    else:
                        self.day = daynum
                        self.renderer.clearInput()
                        self.displayToday(True)

                except ValueError:
                    self.renderer.displayError("Invalid day specified!")

            return NullAction()
        elif inputStr == "month" or inputStr.startswith("month "):
            if " " not in inputStr:
                self.renderer.displayError("No month specified!")
            else:
                _, month = inputStr.split(" ", 1)
                month = month.strip().lower()

                try:
                    monthnum = int(month)

                    if monthnum < 1 or monthnum > 14:
                        self.renderer.displayError("Invalid month specified!")
                    else:
                        self.month = monthnum
                        self.renderer.clearInput()
                        self.displayToday(True)

                except ValueError:
                    self.renderer.displayError("Invalid month specified!")

            return NullAction()
        elif inputStr == "year" or inputStr.startswith("year "):
            if " " not in inputStr:
                self.renderer.displayError("No year specified!")
            else:
                _, year = inputStr.split(" ", 1)
                year = year.strip().lower()

                try:
                    yearnum = int(year)

                    if yearnum < 1 or yearnum > 40:
                        self.renderer.displayError("Invalid year specified!")
                    else:
                        self.year = yearnum
                        self.renderer.clearInput()
                        self.displayToday(True)

                except ValueError:
                    self.renderer.displayError("Invalid year specified!")

            return NullAction()
        elif inputStr[0] == "#":
            # Calendar navigation.
            try:
                result = int(inputStr[1:])
                result -= 1

                if result < 0 or result >= len(self.links):
                    self.renderer.displayError("Unknown event navigation request!")
                else:
                    # Navigate to the page whole cloth.
                    return NavigateAction(self.links[result])
            except ValueError:
                self.renderer.displayError("Invalid event navigation request!")

            return NullAction()

        # Didn't handle this.
        return None


class Renderer:
    def __init__(self, terminal: Terminal) -> None:
        self.terminal = terminal
        self.input = ""
        self.page: Optional[Page] = None
        self.lastError = ""
        self.renderer = RendererCore(terminal, 3, self.terminal.rows - 2)

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
        self.terminal.sendText(f"{page.domain.root}:{page.path}")
        if page.extension and page.extension != "INT":
            self.terminal.sendText(f".{page.extension}")
        if page.name:
            self.terminal.sendText(f" -- {page.name}")
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.clearAutoWrap()

        # Render out the text of the page.
        if page.extension in {"", "TEXT", "DOUB"}:
            if page.data in {"Void", "void", "[Unwritten]"}:
                data = "\n[Unwritten]"
            else:
                data = "\n".join(page.data.split("css"))

            self.renderer = TextRendererCore(self.terminal, 3, self.terminal.rows - 2)
            self.renderer.displayText(data)
        elif page.extension == "INT":
            if page.data == "help":
                commands = {
                    "goto": (
                        "PATH",
                        'Navigate directly to a specified path, such as "NX.HELP:/MAIN". For a more complete '
                        + "description please read the online [!1 Command Help].",
                    ),
                    "cd": (
                        "RELPATH",
                        'Navigate to a new path on the server relative to this one, such as ".." to navigate up one level.',
                    ),
                    "home": (
                        None,
                        "Navigate to the pre-configured system home page.",
                    ),
                    "root": (
                        None,
                        "Navigate to the default page of the current domain.",
                    ),
                    "back": (
                        None,
                        "Navigate to the previous page that was displayed before loading the current page.",
                    ),
                    "random": (
                        None,
                        "Navigate to a completely random page on a GCP server.",
                    ),
                    "prev": (
                        None,
                        "Scroll up one screen's worth of text on the current page.",
                    ),
                    "next": (
                        None,
                        "Scroll down one screen's worth of text on the current page.",
                    ),
                    "top": (
                        None,
                        "Scroll to the top of the text on the current page.",
                    ),
                    "bottom": (
                        None,
                        "Scroll to the bottom of the text on the current page.",
                    ),
                    "set": (
                        "SETTING=VALUE",
                        "Change the value for one of the following settings:\n"
                        + '         * columns - Change the number of columns. Supports "80" and "132".',
                    ),
                    "help": (
                        None,
                        "Display this help screen.",
                    ),
                    "exit": (
                        None,
                        "Exit out of the browser interface.",
                    ),
                }

                helpsections = [
                    "The following commands are available to use at any time:",
                    *[
                        f"    {name}{' [' + args + ']' if args else ''}\n        {desc}"
                        for name, (args, desc) in commands.items()
                    ],
                ]

                self.renderer = TextRendererCore(
                    self.terminal, 3, self.terminal.rows - 2
                )
                self.renderer.displayText("\n\n".join(helpsections))
            elif page.data == "connerr":
                self.renderer = TextRendererCore(
                    self.terminal, 3, self.terminal.rows - 2
                )
                self.renderer.displayText(
                    "\n".join(
                        [
                            "!Error #8: No connection.",
                            "$Could not establish connection with specified server.",
                        ]
                    )
                )
        elif page.extension == "SRCH":
            self.renderer = SearchRendererCore(
                page.domain, self, self.terminal, 3, self.terminal.rows - 2
            )
            self.renderer.displaySearch(page.data)
        elif page.extension == "DICT":
            self.renderer = DictionaryRendererCore(
                self, self.terminal, 3, self.terminal.rows - 2
            )
            self.renderer.displayDictionary(page.data)
        elif page.extension in {"CLND", "CLDR"}:
            self.renderer = CalendarRendererCore(
                self, self.terminal, 3, self.terminal.rows - 2
            )
            self.renderer.displayCalendar(page.data)
        else:
            raise NotImplementedError(f"Page type {page.extension} is unimplemented!")

        # Move cursor to where we expect it for input.
        self.terminal.moveCursor(self.terminal.rows, 1)

    def clearInput(self) -> None:
        # Clear error display.
        self.displayError("")

        self.terminal.moveCursor(self.terminal.rows, 1)
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
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
        elif inputVal in {Terminal.BACKSPACE, Terminal.DELETE}:
            if self.input:
                # Just subtract from input.
                row, col = self.terminal.fetchCursor()

                if col == len(self.input) + 1:
                    # Erasing at the end of the line.
                    self.input = self.input[:-1]

                    col -= 1
                    self.terminal.moveCursor(row, col)
                    self.terminal.sendCommand(Terminal.SET_NORMAL)
                    self.terminal.sendCommand(Terminal.SET_REVERSE)
                    self.terminal.sendText(" ")
                    self.terminal.moveCursor(row, col)
                elif col == 1:
                    # Erasing at the beginning, do nothing.
                    pass
                elif col == 2:
                    # Erasing at the beginning of the line.
                    self.input = self.input[1:]

                    col -= 1
                    self.terminal.moveCursor(row, col)
                    self.terminal.sendCommand(Terminal.SET_NORMAL)
                    self.terminal.sendCommand(Terminal.SET_REVERSE)
                    self.terminal.sendText(self.input)
                    self.terminal.sendText(" ")
                    self.terminal.moveCursor(row, col)
                else:
                    # Erasing in the middle of the line.
                    spot = col - 2
                    self.input = self.input[:spot] + self.input[(spot + 1) :]

                    col -= 1
                    self.terminal.moveCursor(row, col)
                    self.terminal.sendCommand(Terminal.SET_NORMAL)
                    self.terminal.sendCommand(Terminal.SET_REVERSE)
                    self.terminal.sendText(self.input[spot:])
                    self.terminal.sendText(" ")
                    self.terminal.moveCursor(row, col)
        elif inputVal == b"\r":
            # Ignore this.
            pass
        elif inputVal == b"\n":
            # Execute command.
            actual = self.input.strip()
            if not actual:
                return None

            # First, try to delegate to the actual page.
            subResponse = self.renderer.processInput(actual)
            if subResponse is not None:
                return subResponse

            if actual[0] == "!":
                # Link navigation.
                try:
                    link = int(actual[1:])
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
            elif actual == "back":
                return BackAction()
            elif actual == "goto" or actual.startswith("goto "):
                if " " not in actual:
                    self.displayError("No page requested!")
                else:
                    _, newpage = actual.split(" ", 1)
                    newpage = newpage.strip()

                    if ":" in newpage or not newpage.startswith("/"):
                        # Fully qualified path.
                        return NavigateAction(newpage)
                    else:
                        # Assume current domain.
                        return NavigateAction(f"{page.domain.root}:{newpage}")
            elif actual == "home":
                return HomeAction()
            elif actual == "root":
                return NavigateAction(page.domain.root)
            elif actual == "help":
                return HelpAction()
            elif actual == "random":
                return RandomAction()
            elif actual == "exit":
                return ExitAction()
            elif actual == "next":
                self.clearInput()
                self.renderer.pageDown()
            elif actual == "prev":
                self.clearInput()
                self.renderer.pageUp()
            elif actual == "top":
                self.clearInput()
                self.renderer.goToTop()
            elif actual == "bottom":
                self.clearInput()
                self.renderer.goToBottom()
            elif actual == "set" or actual.startswith("set "):
                if " " not in actual:
                    self.displayError("No setting requested!")
                else:
                    _, setting = actual.split(" ", 1)
                    setting = setting.strip()

                    if "=" in setting:
                        setting, value = setting.split("=", 1)
                        setting = setting.strip()
                        value = value.strip()
                    else:
                        setting = setting.strip()
                        value = None

                    return SettingAction(setting, value)
            elif actual == "cd" or actual.startswith("cd "):
                if " " not in actual:
                    self.displayError("No directory specified!")
                else:
                    _, newdir = actual.split(" ", 1)
                    newdir = newdir.strip()

                    newpage = os.path.abspath(os.path.join(page.path, newdir))
                    if not newpage:
                        newpage = "/"

                    return NavigateAction(f"{page.domain.root}:{newpage}")
            else:
                self.displayError(f"Unrecognized command {actual}")
        else:
            # Just add to input.
            row, col = self.terminal.fetchCursor()
            char = inputVal.decode("ascii")

            if col == len(self.input) + 1:
                # Just appending to the input.
                self.input += char
                self.terminal.sendCommand(Terminal.SET_NORMAL)
                self.terminal.sendCommand(Terminal.SET_REVERSE)
                self.terminal.sendText(char)
            else:
                # Adding to mid-input.
                spot = col - 1
                self.input = self.input[:spot] + char + self.input[spot:]

                self.terminal.sendCommand(Terminal.SET_NORMAL)
                self.terminal.sendCommand(Terminal.SET_REVERSE)
                self.terminal.sendText(self.input[spot:])
                self.terminal.moveCursor(row, col + 1)

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
        # Grab input, de-duplicate held down up/down presses so they don't queue up.
        # This can cause the entire message loop to desync as we pile up requests to
        # scroll the screen, ultimately leading in rendering issues and a crash.
        inputVal = terminal.recvInput()
        if inputVal in {Terminal.UP, Terminal.DOWN}:
            while inputVal == terminal.peekInput():
                terminal.recvInput()

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
                    renderer.displayError("No previous page!")
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
            elif isinstance(action, RandomAction):
                randomPage = random.choice(wiki.getAllPages())
                page = nav.navigate(f"{randomPage.domain.root}:{randomPage.path}")
                renderer.displayPage(page)
            elif isinstance(action, HelpAction):
                page = nav.navigate("LOCAL.HELP")
                renderer.displayPage(page)
            elif isinstance(action, ExitAction):
                break

    # Restore the screen before exiting.
    terminal.sendCommand(Terminal.CLEAR_SCREEN)
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
