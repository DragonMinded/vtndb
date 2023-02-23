A VT-100 front-end for the Nth Dimensional Borders Wiki. You will need a VT-100 compatible physical serial terminal to use this! Assuming you have a modern Python 3 installed, ensure the dependencies are available (`python3 -m pip install --upgrade -r requirements.txt`) and then run it like `python3 ndb.py --help`.

Check out a short video demonstration: https://www.youtube.com/watch?v=XHgMCN_gBNQ

What works:
 - Direct page navigation with "goto", loading the homepage with "home", loading the default page of the current domain with "root".
 - Following links using "!" syntax, navigating to the previous page with "back", navigating up with "cd ..".
 - Navigating to random pages using "random".
 - Displaying local command help using the "help" command.
 - Interacting with the wiki search page using the "search" command.
 - Full editing of commands using arrow keys, backspace and all alphanumeric inputs on the VT-100.
 - Scrolling with the arrow keys as well as page up with "prev" and page down with "next".
 - Link highlighting, map drawing and box drawing are mapped to VT-100 character sets.

What doesn't work (yet):
 - Dictionary feature is unimplemented (DICT extension).
 - Calendar feature is unimplemented (CLND/CLDR extension).
 - As a result, the following pages do not render properly:
   - "EQ.NETPEDIA:/ROOT/CALENDAR/CALENDAR"
   - "EQ.NETPEDIA:/ROOT/CULTURE/LANGUAGE/NUNWEI/DICTIONARY"
   - "EQ.NETPEDIA:/ROOT/CULTURE/LANGUAGE/DEORIAN/PROTO/DICTIONARY"
