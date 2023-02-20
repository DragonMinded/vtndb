A VT-100 front-end for the Nth Dimensional Borders Wiki. You will need a VT-100 compatible physical serial terminal to use this! Assuming you have a modern Python 3 installed, ensure the dependencies are available (`python3 -m pip install --upgrade -r requirements.txt`) and then run it like `python3 ndb.py --help`.

Check out a short video demonstration: https://www.youtube.com/watch?v=XHgMCN_gBNQ

What works:
 - Direct page navigation with "goto", loading the homepage with "home", loading the default page of the current domain with "root".
 - Following links using "!" syntax, navigating to the previous page with "back", navigating up with "cd ..".
 - Full editing of commands using arrow keys, backspace and all alphanumeric inputs on the VT-100.
 - Scrolling with the arrow keys as well as page up with "prev" and page down with "next".
 - Link highlighting, map drawing and box drawing are mapped to VT-100 character sets.

What doesn't work (yet):
 - Search feature is unimplemented.
 - Dictionary feature is unimplemented.
 - Inability to exit out of controlling program to return control to another program.
