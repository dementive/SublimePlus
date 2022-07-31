# Sublime Plus
All in one plugin for Sublime Text 4.


# How to Install

Run the following script in the Sublime Text terminal ```(ctrl+` )``` which utilizes git clone for easy installation:
```
import os; path=sublime.packages_path(); (os.makedirs(path) if not os.path.exists(path) else None); window.run_command('exec', {'cmd': ['git', 'clone', 'https://github.com/dementive/SublimePlus', 'SublimePlus'], 'working_dir': path})
```

Alternatively you can download the zip file from github and put the SublimePlus folder (make sure it is named SublimePlus) in the packages folder.
The packages folder can easily be found by going to ```preferences``` in the main menu and selecting ```Browse Packages```.
```
C:\Users\YOURUSERNAME\AppData\Roaming\Sublime Text 3\Packages\SublimePlus
```

# Features

A ton of commands that make using sublime text overall a better experience. 247 color schemes and 3 themes.

There are a wide variety of customizable settings for many of the plugins features that can all be accessed from the main preferences menu.

Main features are: Many new context, tab, and sidebar menu commands. Greatly improved sidebar opening, navigation, and management.
Many new keybindings to make sublime feel more Vim like with better navigation of text and the UI in general.

Many of the commands have keybindings but some are only in certain menus and others are only avaibable in the command palette.
to see all the commands added by the plugin look through the .sublime-menu, .sublime-keymap, and .sublime-commands files.

# File Icons

All 3 of the themes in this plugin support file icon customization via the ```A File Icon``` package found here:

https://packagecontrol.io/packages/A%20File%20Icon

I recommend you install it for a better experience with the sidebar.

# Notes

I wouldn't recommend using too many other plugins that change menus or a lot of keybindings with this plugin.
Sublime Plus changes a lot of menus and keybindings.
So additional plugins can make the sublime experience worse by clogging up the menus and making keybindings confusing.
This is especially true for any other plugins that change the Sidebar.
Sublime Plus was designed to be an all in one plugin so the only other packages you will need to improve sublime are syntax plugins.
This plugin seeks to only extend the existing functionalities of sublime while still keeping the same blazing fast text editor feeling that makes the program great.