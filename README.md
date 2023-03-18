# Sublime Plus
All in one plugin for Sublime Text 4.


# How to Install

Run the following script in the Sublime Text terminal ```(ctrl+` )``` which utilizes git clone for easy installation:
```
import os; path=sublime.packages_path(); (os.makedirs(path) if not os.path.exists(path) else None); window.run_command('exec', {'cmd': ['git', 'clone', 'https://github.com/dementive/SublimePlus', 'SublimePlus'], 'working_dir': path})
```

Alternatively you can download the zip file from github and put the SublimePlus folder (make sure it is named SublimePlus) in the packages folder.
The packages folder can easily be found by going to ```preferences``` in the main menu and selecting ```Browse Packages```. The full path to the plugin should look like this:
```
C:\Users\YOURUSERNAME\AppData\Roaming\Sublime Text 3\Packages\SublimePlus
```

# Features


### Commands

A ton of commands that make using sublime text overall a better experience, these include:

1. Git Gui Override
	- Overrides the repository button command in the status bar to open a custom git gui application. Command Name: 'ggc_open'

2. Notepad
	- Distractionless view command with a lot of settings. Command Name: 'toggle_note_pad'
	- Temporary notepad in a pane that deletes your notes when application is closed. Command Name: 'output_panel_note_pad'

3. Selection
	- Fold Selection. Command Name: 'toggle_fold_selection'
	- Split Selection. Split current selection by a specified character. Command Name: 'split_selection'
	- Selection to Snippet. Make a snippet from the current selection. Command Name: 'selection_to_snippet'
	- Cycle Through Selections. Command Name: 'cycle_through_regions'

4. Movement
	- Fast Move. Move cursor up, down, left, or right by a certain amount of characters. Command Name: 'fast_move'. Args: {direction: "up", extend=true }
	- Sidebar Navigation. With the default sublime plus keybindings file these commands allow navigation of sidebar files and folder with the "ijkl" keys

5. Tab Context Commands that show when rightclicking any tab
	- Rename File in Tab. Command Name: 'rename_file_in_tab'
	- Copy File Path. Command Name: 'copy_file_path'
	- Delete in tab. Command Name: 'tab_context_delete'
	- Toggle Read Only. Command Name: 'toggle_read_only'
	- Sort Tabs. Several different ways to sort tabs

6. Workspace
	- Open Workspace From List. Shows a list of workspaces that are defined in settings and open them. Command Name: 'open_workspace_from_list'. Args: {close: false}

7. Layout
	- Set Layout. Similar to the Origami package but better, use the default keybindings file.

8. Autofold
	- Folds will be remembered when files are closed, this can be disabled with settings.

9. List Handlers
	- Go to Recent. A command pallete list input handler to quickly open recently closed files. Command Name: 'goto_recent'
	- Folder Handler. Easily fold or unfold different levels of a file. Command Name: 'folder_handler'

10. Rainbow Brackets
	
	A simple version of the [Rainbow Brackets](https://github.com/absop/RainbowBrackets) package has been included and has the following commands:
	- Make Rainbow
	- Clear Rainbow
	- Clear Color Schemes

11. Diffy

	A simple version of the [Diffy](https://packagecontrol.io/packages/Diffy) package 
	- Diffy. With 2 tabs side by side in a group use this command and it will draw regions that show the diffs of the two files.

12. Event Listeners
	- Auto Save. Automatically save files under certain conditions, there are a lot of settings so you can define the exact behavior you want.
	- Auto Close Empty Group. When groups are empty they will be automatically closed.
	- Auto Sort Tabs. This is disabled by default and can be enabled in settings to automatically sort opened tabs when opening/closing files.

13. Sidebar Commands/Events
	
	I wouldn't recommend using any other plugins that make changes to the sidebar, your experience with the sidebar will only be worse because almost all available sidebar plugins are integrated into sublime plus.

	- Reveal file in sidebar. Command that will reveal the currently opened file in the sidebar and focus on the sidebar
	- Auto hide sidebar on focus. Disabled by default, will automatically hide the sidebar when focus changes to a view.
	- Auto hide sidebar after keystrokes. Disabled by default, will automatically hide the side bar after X keystrokes have been made.
	- Sidebar Hover. Open the sidebar when hovering over the gutter. Disabled by default, can be enabled in settings.
	- Menu Commands: Copy relative path, copy absolute path, copy name, open/run, duplicate, move, and delete have all been added to the sidebar context menu.

### Color Schemes

45 color custom color schemes are included with Sublime Plus

### Themes

3 custom UI themes are included: Dementive, Github Dark, and Brackets

### Syntax

A "mini" version of the great [Package Dev](https://github.com/SublimeText/PackageDev) plugin that only contains the syntaxes has been included.


### Settings

There are a wide variety of customizable settings for many of the plugins features that can all be accessed from the main preferences menu.


### Keybindings

Many new keybindings have been added to make navigation of the buffer and ui feel more natural.

By default the keybindings file for this plugin is completely commented out, this is to prevent conflicts with other packages and so users can customize keybindings to their liking.
I recommend using the keybindings that are commented out by simply copying the default file into your keybindings in your user folder and then unccomenting all of them, then make any changes you feel are necessary from there.

Keybindings can easily be edited from the main preferences menu.

# Additional Plugins

Some other plugins that work great with sublime plus are:

- [Terminus](https://packagecontrol.io/packages/Terminus) - Fully working terminal directly in sublime text
- [LSP](https://packagecontrol.io/packages/LSP) - Amazing Language Server support that turns sublime into a full feature IDE for almost all languages
- [Git](https://packagecontrol.io/packages/Git) - Very helpful Git integration that adds all the useful git commands directly into the editor
- [Git Gutter](https://packagecontrol.io/packages/GitGutter) - Hover over diffs in the gutter to get a detailed breakdown of git diffs
- [A File Icon](https://packagecontrol.io/packages/A%20File%20Icon) - This is required to have file icons in the sidebar for the custom themes, I highly recommend using it.
