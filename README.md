# vtndb

A VT-100 front-end for the Nth Dimensional Borders Wiki. You will need a VT-100 compatible physical serial terminal to use this! If you're familiar with the source wiki, this navigates and behaves almost identically in every way.

Source Wiki this pulls from: https://echodolls.com/lore/

Check out a short video demonstration: https://www.youtube.com/watch?v=XHgMCN_gBNQ

What works (basically everything):
 - Direct page navigation with "goto", loading the homepage with "home", loading the default page of the current domain with "root".
 - Following links using "!" syntax, navigating to the previous page with "back", navigating up with "cd ..".
 - Navigating to random pages on the current domain using "random".
 - Displaying local command help using the "help" command, including page-specific help.
 - Interacting with special pages, such as the wiki search, calendars and dictionary pages.
 - Full editing of commands using arrow keys, backspace and all alphanumeric inputs on the VT-100.
 - Scrolling with the arrow keys as well as page up with "prev", page down with "next", top of page with "top" and bottom of page with "bottom".
 - Link highlighting, map drawing and box drawing are mapped to VT-100 character sets as closely as possible.

## Running This

If you are non-technical, or you just want to try it out without tinkering, I recommend using `pipx` to install vtndb. For help and instruction on setting up `pipx` on your computer, visit [pipx's installation page](https://pipx.pypa.io/stable/installation/). If you have `pipx` installed already, run the following line to install vtndb on your computer.

```
pipx install git+https://github.com/DragonMinded/vtndb.git
```

Once that completes, run this wiki frontend by typing the following line:

```
vtndb
```

You can also run with `--help`, like the following example, to see all options:

```
vtndb --help
```

Note that original VT-100 terminals, and variants such as the 101 and 102, need the XON/XOFF flow control option enabled. Make sure you enable flow control on the terminal itself, and then use the `--flow` argument to avoid overloading the terminal. Newer terminals such as mid-80s VT-100 clones often do not suffer from this problem and keep up just fine.

## Development

To get started, first install the requirements using a command similar to:

```
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-dev.txt
```

Then, you can run the application similar to:

```
python3 vtndb
```

You can also run with `--help`, like the following example, to see all options:

```
python3 vtndb --help
```
