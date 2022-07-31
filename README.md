# Sublime Plus
All in one plugin for Sublime Text 4.


# How to Install

Run the following script in the Sublime Text terminal ```(ctrl+` )``` which utilizes git clone for easy installation:
```
import os; path=sublime.packages_path(); (os.makedirs(path) if not os.path.exists(path) else None); window.run_command('exec', {'cmd': ['git', 'clone', 'https://github.com/dementive/SublimePlus', 'SublimePlus'], 'working_dir': path})
```

Alternatively you can download the zip file from github and  put the SideBar folder (make sure it is named SideBar) in the packages folder.
This folder can easily be found by going to ```preferences``` in the main menu and selecting ```Browse Packages```.
```
C:\Users\YOURUSERNAME\AppData\Roaming\Sublime Text 3\Packages\SublimePlus
```

# Features

A ton of commands that make using sublime text overall a better experience. Over 250 color schemes and 3 themes.

There are a wide variety of customizable settings for many of the plugins features that can all be accessed from the main preferences menu.

Main features are: Many new context, tab, and sidebar menu commands. Greatly improved sidebar opening, navigation, and management.
Many new keybindings to make sublime feel more Vim like with better navigation of text and the UI in general.

Many of the commands have keybindings but some are only in certain menus and others are only avaibable in the command palette.
to see all the commands added by the plugin look through the .sublime-menu, .sublime-keymap, and .sublime-commands files.