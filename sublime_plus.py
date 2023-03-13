import sublime
import sublime_plugin
import re
import functools
import os
import zlib
import subprocess
import json
import difflib
from os.path import basename

# ------------------------------------------------------
# -                    Plugin Setup                    -
# ------------------------------------------------------

# global settings object that is used in almost all commands, initialized on plugin load
settings = None


def plugin_loaded():
    def load_plugin():
        if settings.get("rainbow_brackets_enabled"):
            ColorSchemeManager.init()
            active_view = sublime.active_window().active_view()
            RainbowBracketsViewManager.check_view_load_listener(active_view)
        else:
            ColorSchemeManager.init()
            active_view = sublime.active_window().active_view()
            RainbowBracketsViewManager.check_view_load_listener(active_view)
            ColorSchemeManager.clear_color_schemes()
            for view in sublime.active_window().views():
                RainbowBracketsViewManager.sweep_view(view)

    global settings
    settings = sublime.load_settings("Sublime Plus.sublime-settings")
    for window in sublime.windows():
        for view in window.views():
            view.run_command("auto_fold_code_restore")

    sublime.set_timeout_async(load_plugin)


def plugin_unloaded():
    if settings:
        if settings.get("rainbow_brackets_enabled"):
            ColorSchemeManager.prefs.clear_on_change("color_scheme")
            ColorSchemeManager.settings.clear_on_change("default_config")
        else:
            ColorSchemeManager.prefs.clear_on_change("color_scheme")
            ColorSchemeManager.settings.clear_on_change("default_config")
            ColorSchemeManager.clear_color_schemes()
            for view in sublime.active_window().views():
                RainbowBracketsViewManager.sweep_view(view)


# ------------------------------------------------------
# -                      Commands                      -
# ------------------------------------------------------

# Notepad

class ToggleNotePadCommand(sublime_plugin.ApplicationCommand):

    def __init__(self):
        self.notepad_toggle = False
        self.old_scheme = None
        self.original_centered_setting = None

    def run(self):
        window = sublime.active_window()
        view = window.active_view()

        if not self.notepad_toggle:
            # Make notepad
            if window.is_menu_visible() is True:
                window.set_menu_visible(False)
            window.set_sidebar_visible(False)
            if not settings.get("show_tabs_in_notepad"):
                window.set_tabs_visible(False)
            if not settings.get("show_status_bar_in_notepad"):
                window.set_status_bar_visible(False)
            if not settings.get("show_minimap_in_notepad"):
                window.set_minimap_visible(False)

            if not settings.get("show_gutter_in_notepad"):
                view.settings().set('gutter', False)
            view.settings().set("toggle_status_bar", False)
            window.run_command('hide_panel')
            self.old_scheme = view.settings().get("color_scheme")
            self.original_centered_setting = view.settings().get("draw_centered")
            if settings.get("notepad_color_scheme_mode") == "Light":
                view.settings().set("color_scheme", "NotepadLight.hidden-color-scheme")
            elif settings.get("notepad_color_scheme_mode") == "Dark":
                view.settings().set("color_scheme", "Notepad.hidden-color-scheme")
            if settings.get("draw_centered_notepad"):
                view.settings().set("draw_centered", True)
            self.notepad_toggle = True
        else:
            # Revert to default state
            window.set_tabs_visible(True)
            window.set_status_bar_visible(True)
            window.set_minimap_visible(True)
            view.settings().set("gutter", True)
            view.settings().set("toggle_status_bar", True)
            if settings.get("notepad_color_scheme_mode") != "Default":
                view.settings().set("color_scheme", self.old_scheme)
            if settings.get("draw_centered_notepad"):
                # If draw_centered was already on, turn it back on. Else turn it off
                if self.original_centered_setting:
                    view.settings().set("draw_centered", True)
                else:
                    view.settings().set("draw_centered", False)
            self.notepad_toggle = False


class OutputPanelNotePadCommand(sublime_plugin.ApplicationCommand):

    def __init__(self):
        self.shown = False

    def panel_creation(self, window, view):
        window.focus_view(view)
        if settings.get("temp_notepad_color_scheme_mode") == "Light":
            view.settings().set("color_scheme", "NotepadLight.hidden-color-scheme")
        elif settings.get("temp_notepad_color_scheme_mode") == "Dark":
            view.settings().set("color_scheme", "Notepad.hidden-color-scheme")
        view.assign_syntax("scope:text.notes")
        view.settings().set("font_size", settings.get("temp_notepad_font_size"))
        if not settings.get("show_gutter_in_notepad"):
            view.settings().set('gutter', False)
        if settings.get("draw_centered_temp_notepad"):
            view.settings().set("draw_centered", True)
        self.shown = True

    # def save_output_panel_contents(self):
    #     window = sublime.active_window()
    #     if window.find_output_panel("NotePad") == None:
    #         return 1
    #     view = window.find_output_panel("NotePad")
    #     region = sublime.Region(0, len(self.view))
    #     string = view.substr(region)
    #     print(string)

    def run(self):
        window = sublime.active_window()
        if window.find_output_panel("NotePad") is None:
            panel = window.create_output_panel("NotePad")
            window.run_command("show_panel", {"panel": "output.NotePad"})
            self.panel_creation(window, panel)
        else:
            window.run_command("show_panel", {"panel": "output.NotePad"})
            view = window.find_output_panel("NotePad")
            self.panel_creation(window, view)


# Selection and movement commands

class ToggleFoldSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        selection = view.sel()

        def is_folded(region):
            return self.view.unfold(region)

        for region in selection:
            if not is_folded(region):
                self.view.fold(region)
            else:
                self.view.unfold(region)
            str_buffer = view.substr(region)
            if len(str_buffer) == 0:
                sublime.set_timeout(lambda: sublime.status_message(
                    'There is no text selected!'), 0)


class SplitSelectionCommand(sublime_plugin.TextCommand):

    def run(self, edit, separator=None):

        self.savedSelection = [r for r in self.view.sel()]

        selectionSize = sum(
            map(lambda region: region.size(), self.savedSelection))
        if selectionSize == 0:
            # nothing to do
            sublime.status_message("Cannot split an empty selection.")
            return

        if separator is not None:
            self.splitSelection(separator)
        else:
            onConfirm, onChange = self.getHandlers()

            inputView = sublime.active_window().show_input_panel(
                "Separating character(s) for splitting the selection",
                " ",
                onConfirm,
                onChange,
                self.restoreSelection
            )

            inputView.run_command("select_all")

    def getHandlers(self):
        live_split_selection = settings.get("live_split_selection")

        if live_split_selection:
            onConfirm = None
            onChange = self.splitSelection
        else:
            onConfirm = self.splitSelection
            onChange = None

        return (onConfirm, onChange)

    def restoreSelection(self):

        selection = self.view.sel()
        selection.clear()
        for region in self.savedSelection:
            selection.add(region)

    def splitSelection(self, separator):

        view = self.view
        newRegions = []

        for region in self.savedSelection:
            currentPosition = region.begin()
            regionString = view.substr(region)

            if separator:
                subRegions = regionString.split(separator)
            else:
                # take each character separately
                subRegions = list(regionString)

            for subRegion in subRegions:
                newRegion = sublime.Region(
                    currentPosition,
                    currentPosition + len(subRegion)
                )
                newRegions.append(newRegion)
                currentPosition += len(subRegion) + len(separator)

        selection = view.sel()
        selection.clear()
        for region in newRegions:
            selection.add(region)

        window = sublime.active_window()
        window.run_command("move", {"by": "characters", "forward": True})
        window.run_command("move", {"by": "characters", "forward": False})


class SelectionToSnippetCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        selection = view.sel()
        str_out = ""

        for region in selection:
            str_buffer = view.substr(region)
            if len(str_buffer) == 0:
                sublime.set_timeout(lambda: sublime.status_message(
                    'There is no text selected!'), 0)
            else:
                str_out = str_out + "\n" + str_buffer

        window = sublime.active_window()
        window.run_command('new_file')
        snippet_view = window.active_view()
        snippet_view.set_name("snippet.sublime-snippet")
        snippet_view.run_command(
            "insert_snippet_contents", {'string': str_out})


class InsertSnippetContentsCommand(sublime_plugin.TextCommand):
    def run(self, edit, string):
        snippet_head = "<snippet>\n\t<content><![CDATA["
        snippet_foot = "\n\t]]></content>\n\t<!-- ${1:Selection Field 1}.${2:Selection Field 2} -->\n\t<tabTrigger>add_centralization</tabTrigger>\n\t<scope>source.python</scope>\n\t<description>Description</description>\n</snippet>"
        string = snippet_head + string + snippet_foot
        self.view.insert(edit, len(self.view), string)


class CycleThroughRegionsCommand(sublime_plugin.TextCommand):

    def run(self, edit):

        view = self.view
        visibleRegion = view.visible_region()
        selectedRegions = view.sel()

        nextRegion = None

        for region in selectedRegions:
            str_buffer = view.substr(region)
            if len(str_buffer) == 0:
                sublime.set_timeout(lambda: sublime.status_message(
                    'There is no text selected!'), 0)
            if region.end() > visibleRegion.b:
                nextRegion = region
                break

        if nextRegion is None:
            nextRegion = selectedRegions[0]

        view.show(nextRegion, False)


class MoveToTopOfFileCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.sel().clear()
        selection = sublime.Region(0, 0)
        self.view.sel().add(selection)
        self.view.show(selection)


class MoveToBottomOfFileCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.sel().clear()
        eof = len(self.view)
        selection = sublime.Region(eof, eof)
        self.view.sel().add(selection)
        self.view.show(selection)


class FastMoveCommand(sublime_plugin.TextCommand):
    def run(self, edit, direction, extend=False):
        window = sublime.active_window()
        if (direction == "up"):
            for i in range(settings.get("fast_move_horizontal_character_amount")):
                window.run_command(
                    "move", {"by": "lines", "forward": False, "extend": extend})
        if (direction == "down"):
            for i in range(settings.get("fast_move_horizontal_character_amount")):
                window.run_command(
                    "move", {"by": "lines", "forward": True, "extend": extend})
        if (direction == "left"):
            for i in range(settings.get("fast_move_horizontal_character_amount")):
                window.run_command(
                    "move", {"by": "characters", "forward": False, "extend": extend})
        if (direction == "right"):
            for i in range(settings.get("fast_move_horizontal_character_amount")):
                window.run_command(
                    "move", {"by": "characters", "forward": True, "extend": extend})


# Tab Context commands

class RenameFileInTabCommand(sublime_plugin.TextCommand):
    def run(self, edit, args=None, index=-1, group=-1, **kwargs):
        w = self.view.window()
        views = w.views_in_group(group)
        view = views[index]

        full_path = view.file_name()
        if full_path is None:
            return

        directory, fn = os.path.split(full_path)
        v = w.show_input_panel("New file name:",
                               fn,
                               functools.partial(
                                   self.on_done, full_path, directory),
                               None,
                               None)
        name, ext = os.path.splitext(fn)

        v.sel().clear()
        v.sel().add(sublime.Region(0, len(name)))

    def on_done(self, old, directory, fn):
        new = os.path.join(directory, fn)

        if new == old:
            return

        try:
            if os.path.isfile(new):
                if old.lower() != new.lower() or os.stat(old).st_ino != os.stat(new).st_ino:
                    # not the same file (for case-insensitive OSes)
                    raise OSError("File already exists")

            os.rename(old, new)

            v = self.view.window().find_open_file(old)
            if v:
                v.retarget(new)
        except OSError as e:
            sublime.error_message("Unable to rename: " + str(e))
        except Exception as e:
            sublime.error_message("Unable to rename: " + str(e))


class CopyFilePath(sublime_plugin.TextCommand):
    def run(self, edit, args=None, index=-1, group=-1, **kwargs):
        w = self.view.window()
        views = w.views_in_group(group)
        view = views[index]

        file_name = view.file_name()
        if file_name is None:
            return

        sublime.set_clipboard(file_name)


class TabContextTerminalCommand(sublime_plugin.TextCommand):
    def run(self, edit, args=None, index=-1, group=-1, **kwargs):
        window = self.view.window()
        views = window.views_in_group(group)
        view = views[index]

        file_name = view.file_name()

        if file_name:
            env = os.environ.copy()
            res_str = file_name[file_name.rfind("\\"):len(file_name)]
            file_name = file_name.replace(res_str, "")
            subprocess.Popen("cmd.exe", env=env, cwd=file_name)
        else:
            sublime.set_timeout(lambda: sublime.status_message(
                'Selected file cannot be opened in Terminal.'), 0)

    def is_enabled(self):
        if sublime.platform() == "windows":
            return True
        else:
            return False

    def is_visible(self):
        if sublime.platform() == "windows":
            return True
        else:
            return False


class TabContextDeleteCommand(sublime_plugin.TextCommand):
    def run(self, edit, args=None, index=-1, group=-1, **kwargs):
        window = self.view.window()
        views = window.views_in_group(group)
        view = views[index]
        file_name = view.file_name()

        if file_name:
            if sublime.ok_cancel_dialog(f"Are you sure you want to delete\n{file_name}?", "Delete"):
                import Default.send2trash as send2trash
                try:
                    send2trash.send2trash(file_name)
                    view.close()
                except:
                    window.status_message("Unable to delete")
        else:
            sublime.set_timeout(lambda: sublime.status_message(
                'Selected file cannot be deleted.'), 0)


# Workspace

class CloseWindowListInputHandler(sublime_plugin.ListInputHandler):

    def name(self):
        return 'close'

    def list_items(self):
        return [
            ('Close Current Workspace', True),
            ('Keep Current Workspace', False)
        ]


class OpenWorkspaceFromListCommand(sublime_plugin.WindowCommand):

    def input_description(self):
        return "Select Workspace"

    def input(self, args):
        if 'workspace' not in args:
            return WorkspaceListInputHandler()
        if 'close' not in args:
            return CloseWindowListInputHandler()

    def run(self, workspace, close):
        if workspace is not None:
            workspace = workspace + ".sublime-workspace"
            project_directories = settings.get(
                'sublime_workspace_directories_list')
            if len(project_directories) > 0:
                # space_path = os.path.abspath(workspace)
                s_workspace_file = re.compile("^.*?\.sublime-workspace$")
                results = []
                for directory in project_directories:
                    for name in os.listdir(directory):
                        if s_workspace_file.match(workspace):
                            if name == workspace:
                                workspace = directory + "\\" + name
                                window = sublime.active_window()
                                if close:
                                    window.run_command("close_workspace")
                                    window.run_command("close_pane")
                                    os.startfile(workspace)
                                else:
                                    os.startfile(workspace)
        else:
            sublime.set_timeout(lambda: sublime.status_message(
                'No directories have been added to the workspace directories list. See Sublime Plus.sublime-setting for more info.'), 0)


# Sidebar navigation commands

class TreeViewGoToParentNode(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command('move_to', {'to': 'bol', 'extend': False})


class TreeViewGoToRootNode(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command('move', {'by': 'characters', 'forward': False})


class TreeViewGoToChildNode(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command('move_to', {'to': 'eol', 'extend': False})


class TreeViewMoveDown(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command('move', {'by': 'lines', 'forward': True})


class TreeViewMoveLeft(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command('move', {'by': 'characters', 'forward': False})


class TreeViewMoveRight(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command('move', {'by': 'characters', 'forward': True})


class TreeViewMoveUp(sublime_plugin.WindowCommand):
    def run(self):
        self.window.run_command('move', {'by': 'lines', 'forward': False})


# Layout commands

class PolyfillSetLayoutCommand(sublime_plugin.WindowCommand):
    def run(self, cols, rows, cells):
        num_groups_before = self.window.num_groups()
        active_group_before = self.window.active_group()

        self.window.run_command('set_layout', {
            'cols': cols,
            'rows': rows,
            'cells': cells
        })

        if num_groups_before == self.window.num_groups():
            self.window.focus_group(active_group_before)
            return

        if len(self.window.views_in_group(active_group_before)) < 2:
            return

        view = self.window.active_view_in_group(active_group_before)
        self.window.set_view_index(view, self.window.active_group(), 0)


# Autofold

class AutoFoldCommandBase():
    """
        Base class for common methods for auto fold commands
    """

    def __init__(self):
        self.__storage_file__ = 'AutoFoldCode.sublime-settings'
        self.CURRENT_STORAGE_VERSION = 1
        self.MAX_BUFFER_SIZE_DEFAULT = 1000000

    def _save_view_data(self, view, clean_existing_versions):
        """
            Save the folded regions of the view to disk.
        """
        file_name = view.file_name()
        if file_name is None:
            return

        # Skip saving data if the file size is larger than `max_buffer_size`.
        settings = self._load_storage_settings(save_on_reset=False)
        if view.size() > settings.get("max_buffer_size", self.MAX_BUFFER_SIZE_DEFAULT):
            return

        def _save_region_data(data_key, regions):
            all_data = settings.get(data_key)
            if regions:
                if clean_existing_versions or file_name not in all_data:
                    all_data[file_name] = {}

                view_data = all_data.get(file_name)
                view_data[view_content_checksum] = regions
            else:
                all_data.pop(file_name, None)

            settings.set(data_key, all_data)

        view_content_checksum = self._compute_view_content_checksum(view)

        # Save folds
        fold_regions = [(r.a, r.b) for r in view.folded_regions()]
        _save_region_data("folds", fold_regions)

        # Save selections if set
        if settings.get("save_selections") is True:
            selection_regions = [(r.a, r.b) for r in view.selection]
            _save_region_data("selections", selection_regions)

        # Save settings
        sublime.save_settings(self.__storage_file__)

    def _clear_cache(self, name):
        """
            Clears the cache. If name is '*', it will clear the whole cache.
            Otherwise, pass in the file_name of the view to clear the view's cache.
        """
        settings = self._load_storage_settings(save_on_reset=False)

        def _clear_cache_section(data_key):
            all_data = settings.get(data_key)
            file_names_to_delete = [
                file_name for file_name in all_data if name == '*' or file_name == name]
            for file_name in file_names_to_delete:
                all_data.pop(file_name)
            settings.set(data_key, all_data)

        _clear_cache_section("folds")
        _clear_cache_section("selections")
        sublime.save_settings(self.__storage_file__)

    def _load_storage_settings(self, save_on_reset):
        """
            Loads the settings, resetting the storage file, if the version is old (or broken).
            Returns the settings instance
        """
        try:
            settings = sublime.load_settings(self.__storage_file__)
        except Exception as e:
            print('[AutoFoldCode.] Error loading settings file (file will be reset): ', e)
            save_on_reset = True

        if self._is_old_storage_version(settings):
            settings.set("max_buffer_size", self.MAX_BUFFER_SIZE_DEFAULT)
            settings.set("version", self.CURRENT_STORAGE_VERSION)
            settings.set("folds", {})
            settings.set("selections", {})

            if save_on_reset:
                sublime.save_settings(self.__storage_file__)

        return settings

    def _is_old_storage_version(self, settings):
        settings_version = settings.get("version", 0)

        # Consider the edge case of a file named "version".
        return not isinstance(settings_version, int) or settings_version < self.CURRENT_STORAGE_VERSION

    def _compute_view_content_checksum(self, view):
        """
            Returns the checksum in Python hex string format.
            The view content returned is always the latest version, even when closing without saving.
        """
        view_content = view.substr(sublime.Region(0, view.size()))
        int_crc32 = zlib.crc32(view_content.encode('utf-8'))
        return hex(int_crc32 % (1 << 32))


class AutoFoldCodeListener(sublime_plugin.EventListener, AutoFoldCommandBase):
    """
        Listen to changes in views to automatically save code folds.
    """

    def on_load_async(self, view):
        view.run_command("auto_fold_code_restore")

    def on_post_save_async(self, view):
        # Keep only the latest version, since it's guaranteed that on open, the
        # saved version of the file is opened.
        if settings.get("save_folds_on_save"):
            AutoFoldCommandBase.__init__(self)
            self._save_view_data(view, True)

    # Listening on close events is required to handle hot exit, for whom there is
    # no available listener.
    def on_close(self, view):
        # In this case, we don't clear the previous versions view data, so that on
        # open, depending on the previous close being a hot exit or a regular window
        # close, the corresponding view data is retrieved.
        #
        # If a user performs multiple modifications and hot exits, the view data for
        # each version is stored. This is acceptable, since the first user initiated
        # save will purge the versions and store only the latest.
        self._save_view_data(view, False)

    def on_text_command(self, view, command_name, args):
        if command_name == 'unfold_all' and view.file_name() is not None:
            self._clear_cache(view.file_name())


class AutoFoldCodeClearAllCommand(sublime_plugin.WindowCommand, AutoFoldCommandBase):
    """
        Clears all the saved code folds and unfolds all the currently open windows.
    """

    def run(self):
        AutoFoldCommandBase.__init__(self)
        self._clear_cache('*')
        self.window.run_command('auto_fold_code_unfold_all')


class AutoFoldCodeClearCurrentCommand(sublime_plugin.WindowCommand, AutoFoldCommandBase):
    """
        Clears the cache for the current view, and unfolds all its regions.
    """

    def run(self):
        AutoFoldCommandBase.__init__(self)
        view = self.window.active_view()
        if view and view.file_name():
            view.unfold(sublime.Region(0, view.size()))
            self._clear_cache(view.file_name())

    def is_enabled(self):
        view = self.window.active_view()
        return view is not None and view.file_name() is not None


class AutoFoldCodeUnfoldAllCommand(sublime_plugin.WindowCommand):
    """
        Unfold all code folds in all open files.
    """

    def run(self):
        for window in sublime.windows():
            for view in window.views():
                view.unfold(sublime.Region(0, view.size()))


class AutoFoldCodeRestoreCommand(sublime_plugin.TextCommand, AutoFoldCommandBase):

    def run(self, edit):
        AutoFoldCommandBase.__init__(self)
        file_name = self.view.file_name()
        if file_name is None:
            return

        # Skip restoring folds if the file size is larger than `max_buffer_size`.
        settings = self._load_storage_settings(save_on_reset=True)
        if self.view.size() > settings.get("max_buffer_size", self.MAX_BUFFER_SIZE_DEFAULT):
            return

        view_content_checksum = self._compute_view_content_checksum(self.view)

        # Restore folds
        view_folds_data = settings.get("folds").get(file_name, {})
        for a, b in view_folds_data.get(view_content_checksum, []):
            self.view.fold(sublime.Region(a, b))

        # Restore selections
        if settings.get("save_selections"):
            view_selection_data = settings.get("selections").get(file_name, {})
            self.view.selection.clear()
            for a, b in view_selection_data.get(view_content_checksum, []):
                self.view.selection.add(sublime.Region(a, b))


# Keybinding commands


class DoubleClickAtCaretCommand(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        view = self.view
        # enumerate through each selection, while keeping a note of which index it is and looking up the window coordinates
        for idx, vector in enumerate(map(lambda sel: view.text_to_window(sel.begin()), view.sel())):
            # emulate a double click at those coordinates
            view.run_command('drag_select', {
                'event': {
                    'button': 1,
                    'count': 2,
                    'x': vector[0],
                    'y': vector[1]
                },
                'by': 'words',
                # if there are multiple selections, act like pressing Ctrl while double clicking - otherwise we will end up with only one selection. The first double click should replace any existing selections unless told otherwise.
                'additive': idx > 0 or kwargs.get('additive', False)
            })


class CommentsAwareEnterCommand(sublime_plugin.TextCommand):
    """
    Context aware Enter handler.
    Preserves line comments scope (by adding escaping chars as needed)
    and auto indents in comments.
    """

    def run(self, edit):
        for region in reversed(self.view.sel()):
            pos = region.end()
            COMMENT_STYLES = {
                'number-sign': ['#'],
                'graphql': ['#'],
                'double-slash': ['//'],
                'double-dash': ['--'],
                'semicolon': [';'],
                'percentage': ['%'],
                'erlang': ['%'],
                'documentation': ['///', '//!'],
            }
            delims = COMMENT_STYLES.get(self.comment_style(self.view, pos), [])
            line = self.line_start_str(self.view, pos)

            replacement = "\n"
            for delim in delims:
                if delim not in line:
                    continue
                start, delim, end = re.split(
                    r'(%s+)' % re.escape(delim), line, 1)
                start = re.sub(r'\S', ' ', start)
                if self.view.settings().get('linecomments_label_indent', True):
                    end = re.search(r'^\s*([A-Z]+:|-)?\s*', end).group()
                else:
                    end = re.search(r'^\s*(-)?\s*', end).group()
                if '-' not in end:
                    end = ' ' * len(end)
                replacement = "\n" + start + delim + end
                break
            else:
                # If no delim before cursor fall back to Sublime Text default
                self.view.run_command("insert", {"characters": "\n"})
                return

            self.view.erase(edit, region)
            self.view.insert(edit, region.begin(), replacement)

    def line_start(self, view, pos):
        line = view.line(pos)
        return sublime.Region(line.begin(), pos)

    def line_start_str(self, view, pos):
        return view.substr(self.line_start(view, pos))

    def comment_style(self, view, pos):
        parsed_scope = self.parse_scope(self.scope_name(view, pos))
        return self.first(vec[2] for vec in parsed_scope if vec[:2] == ['comment', 'line'])

    def scope_name(self, view, pos):
        return view.scope_name(pos)

    def parse_scope(self, scope_name):
        return [name.split('.') for name in scope_name.split()]

    def first(self, seq):
        return next(iter(seq), None)


class ClearConsoleCommand(sublime_plugin.ApplicationCommand):
    """
    Clear out the Sublime console by temporarily setting the scroll back length
    to a single line and outputting a line, causing the history to be dropped.
    """

    def run(self):
        s = sublime.load_settings('Preferences.sublime-settings')
        scrollback = s.get('console_max_history_lines')
        s.set('console_max_history_lines', 1)
        print("")
        s.set('console_max_history_lines', scrollback)


# Folding Commands

class FolderHandler(sublime_plugin.TextCommand):

    def input_description(self):
        return "Fold Level"

    def input(self, args):
        if 'level' not in args:
            return FoldingInputHandler()

    def run(self, edit, level):
        if level != "Unfold All":
            self.view.run_command("fold_by_level", {"level": int(level)})
        else:
            self.view.run_command("unfold_all")


class FoldingInputHandler(sublime_plugin.ListInputHandler):

    def name(self):
        return 'level'

    def list_items(self):
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "Unfold All"]
        return keys


# Rainbow Brackets


class Tree:
    __slots__ = ["opening", "closing", "contain"]

    def __init__(self, opening, closing, contain):
        self.opening = opening
        self.closing = closing
        self.contain = contain


class RainbowBracketsControllerCommand(sublime_plugin.WindowCommand):
    def run(self, action):
        view = self.window.active_view()

        if action == "make rainbow":
            RainbowBracketsViewManager.color_view(view)

        elif action == "clear rainbow":
            RainbowBracketsViewManager.sweep_view(view)

        elif action == "clear color schemes":
            ColorSchemeManager.clear_color_schemes()

    def is_visible(self):
        if settings.get("rainbow_brackets_enabled"):
            return True
        else:
            return False


class RainbowBracketsViewListener():
    def __init__(self, view, syntax, config):
        self.bad_key = config["bad_key"]
        self.bad_scope = config["bad_scope"]
        self.coloring = config["coloring"]
        self.keys = config["keys"]
        self.brackets = config["bracket_pairs"]
        self.pattern = config["pattern"]
        self.scopes = config["scopes"]
        self.selector = config["selector"]
        self.color_number = len(self.keys)
        self.bad_bracket_regions = []
        self.bracket_regions_lists = []
        self.bracket_regions_trees = []
        self.regexp = re.compile(self.pattern)
        self.syntax = syntax
        self.view = view

    def __del__(self):
        self.clear_bracket_regions()

    def load(self):
        self.check_bracket_regions()

    def check_bracket_regions(self):
        if self.coloring:
            self.construct_bracket_trees_and_lists()
            self.clear_bracket_regions()
            if self.bracket_regions_lists:
                for level, regions in enumerate(self.bracket_regions_lists):
                    self.view.add_regions(
                        self.keys[level],
                        regions,
                        scope=self.scopes[level],
                        flags=sublime.DRAW_NO_OUTLINE | sublime.PERSISTENT)
            if self.bad_bracket_regions:
                self.view.add_regions(
                    self.bad_key,
                    self.bad_bracket_regions,
                    scope=self.bad_scope,
                    flags=sublime.DRAW_EMPTY | sublime.PERSISTENT)
        else:
            self.construct_bracket_trees()

    def clear_bracket_regions(self):
        self.view.erase_regions(self.bad_key)
        for key in self.keys:
            self.view.erase_regions(key)

    def construct_bracket_trees(self):
        self.bracket_regions_trees = []

        brackets = self.brackets
        selector = self.selector
        number_levels = self.color_number
        match_selector = self.view.match_selector
        view_full_text = self.view.substr(sublime.Region(0, self.view.size()))
        match_iterator = self.regexp.finditer(view_full_text)

        opening_stack = []
        tree_node_stack = [Tree(None, None, self.bracket_regions_trees)]
        tree_node_stack_append = tree_node_stack.append
        opening_stack_append = opening_stack.append
        tree_node_stack_pop = tree_node_stack.pop
        opening_stack_pop = opening_stack.pop

        def handle(bracket, region):
            if bracket in brackets:
                tree_node_stack_append(Tree(region, None, []))
                opening_stack_append(bracket)

            elif opening_stack and bracket == brackets[opening_stack[-1]]:
                opening_stack_pop()
                node = tree_node_stack_pop()
                node.closing = region
                tree_node_stack[-1].contain.append(node)

        self.handle_matches(selector, match_selector, match_iterator, handle)

    def construct_bracket_trees_and_lists(self):
        self.bad_bracket_regions = []
        self.bracket_regions_lists = []
        self.bracket_regions_trees = []

        brackets = self.brackets
        selector = self.selector
        number_levels = self.color_number
        match_selector = self.view.match_selector
        view_full_text = self.view.substr(sublime.Region(0, self.view.size()))
        match_iterator = self.regexp.finditer(view_full_text)

        opening_stack = []
        tree_node_stack = [Tree(None, None, self.bracket_regions_trees)]
        tree_node_stack_append = tree_node_stack.append
        opening_stack_append = opening_stack.append
        tree_node_stack_pop = tree_node_stack.pop
        opening_stack_pop = opening_stack.pop

        regions_by_level = [list() for i in range(number_levels)]
        appends_by_level = [rs.append for rs in regions_by_level]

        def handle(bracket, region):
            if bracket in brackets:
                tree_node_stack_append(Tree(region, None, []))
                opening_stack_append(bracket)

            elif opening_stack and bracket == brackets[opening_stack[-1]]:
                opening_stack_pop()
                node = tree_node_stack_pop()
                node.closing = region
                tree_node_stack[-1].contain.append(node)
                level = len(opening_stack) % number_levels
                appends_by_level[level](node.opening)
                appends_by_level[level](node.closing)
            else:
                self.bad_bracket_regions.append(region)

        self.handle_matches(selector, match_selector, match_iterator, handle)
        self.bracket_regions_lists = [ls for ls in regions_by_level if ls]

    def handle_matches(self, selector, match_selector, match_iterator, handle):
        if selector:
            for m in match_iterator:
                if match_selector(m.span()[0], selector):
                    continue
                handle(m.group(), sublime.Region(*m.span()))
        else:
            for m in match_iterator:
                handle(m.group(), sublime.Region(*m.span()))


# Diffy

class RegionToDraw(object):
    def __init__(self, line_number, start):
        self.line_number = line_number
        self.start = start

    def get_data(self):
        return (self.line_number, self.start)

    def __str__(self):
        return ""

    def __repr__(self):
        return self.__str__()


class LineToDraw(RegionToDraw):
    def __init__(self, line_number, start):
        super(LineToDraw, self).__init__(line_number, start)

    def get_region(self, view):
        point = view.text_point(self.line_number, 0)
        return view.line(point)

    def __str__(self):
        return "LineToDraw: {line_number}".format(line_number=self.line_number)


class WordToDraw(RegionToDraw):
    def __init__(self, line_number, start, end):
        super(WordToDraw, self).__init__(line_number, start)
        self.end = end

    def get_region(self, view):
        point_start = view.text_point(self.line_number, self.start)
        point_end = view.text_point(self.line_number, self.end)

        #  take advantage of sublime's API to highlight a word
        return view.word(point_start)

    def __str__(self):
        return "WordToDraw: {line_number}: ({start}, {end})".format(line_number=self.line_number, start=self.start, end=self.end)


class Diffy(object):
    def parse_diff_list(self, lst):
        #  add a sentinal at the end
        lst.append("$3nt1n3L\n")

        #  variables
        diff = []
        line_num = -1
        pre_diff_code = ""
        pre_line = ""

        for line in lst:
            line_num += 1
            diff_code = line[0]

            #  the content of the original line
            pre_line_content = pre_line[2:]
            line_content = line[2:]

            #  detect a change
            if diff_code == '?':
                line_num -= 1
                continue
            elif diff_code == '+':
                line_num -= 1

            if pre_diff_code == '-' and diff_code == '+':
                if line_content == "" or line_content.isspace():
                    r = LineToDraw(line_num - 1, 0)
                    diff.append(r)
                else:
                    s = difflib.SequenceMatcher(None, pre_line_content, line_content)
                    for tag, i1, i2, j1, j2 in s.get_opcodes():
                        if tag == 'insert':
                            r = WordToDraw(line_num, j1, j2)
                            diff.append(r)
                        elif tag == 'delete' or tag == 'replace':
                            r = WordToDraw(line_num, i1, i2)
                            diff.append(r)
            elif pre_diff_code == '-':
                r = LineToDraw(line_num - 1, 0)
                diff.append(r)

            #  tracking
            pre_line = line
            pre_diff_code = diff_code

        return diff

    def calculate_diff(self, text1, text2):
        d = difflib.Differ()
        result1 = list(d.compare(text1, text2))
        diff_1 = self.parse_diff_list(result1)

        result2 = list(d.compare(text2, text1))
        diff_2 = self.parse_diff_list(result2)

        return diff_1, diff_2


class DiffyCommand(sublime_plugin.TextCommand):
    def get_entire_content(self, view):
        selection = sublime.Region(0, view.size())
        content = view.substr(selection)
        return content

    def clear(self, view):
        """
            return the marked lines
        """
        view.erase_regions('highlighted_lines')

    def draw_difference(self, view, diffs):
        self.clear(view)

        lines = [d.get_region(view) for d in diffs]

        view.add_regions(
            'highlighted_lines',
            lines,
            'keyword',
            'dot',
            sublime.DRAW_OUTLINED
        )

        return lines

    def set_view_point(self, view, lines):
        if len(lines) > 0:
            view.show(lines[0])

    def run(self, edit, **kwargs):
        diffy = Diffy()
        window = self.view.window()

        action = kwargs.get('action', None)

        view_1 = window.selected_sheets()[0].view() if len(window.selected_sheets()) >= 2 else window.active_view_in_group(0)
        view_2 = window.selected_sheets()[1].view() if len(window.selected_sheets()) >= 2 else window.active_view_in_group(1)

        if action == 'clear':
            if view_1:
                self.clear(view_1)
            if view_2:
                self.clear(view_2)
        else:
            # make sure there are 2 columns side by side
            if view_1 and view_2:
                text_1 = self.get_entire_content(view_1)
                text_2 = self.get_entire_content(view_2)

                if len(text_1) > 0 and len(text_2) > 0:
                    diff_1, diff_2 = diffy.calculate_diff(text_1.split('\n'), text_2.split('\n'))

                    highlighted_lines_1 = self.draw_difference(view_1, diff_1)
                    highlighted_lines_2 = self.draw_difference(view_2, diff_2)

                    self.set_view_point(view_1, highlighted_lines_1)
                    self.set_view_point(view_2, highlighted_lines_2)


# ------------------------------------------------------
# -                  Event Listeners                   -
# ------------------------------------------------------


class RainbowBracketsViewManager(sublime_plugin.EventListener):
    configs_by_stx = {}
    syntaxes_by_ext = {}
    view_listeners = {}
    is_ready = False

    @classmethod
    def load_config(cls, settings):
        cls.is_ready = False

        default_config = settings.get("default_config", {})
        configs_by_stx = settings.get("syntax_specific", {})
        syntaxes_by_ext = {}

        for syntax, config in configs_by_stx.items():
            for key in ("enabled", "coloring"):
                if key not in config:
                    config[key] = True
            for key in default_config.keys():
                if key not in config:
                    config[key] = default_config[key]
            for ext in config.get("extensions", []):
                syntaxes_by_ext[ext] = syntax

        if "coloring" not in default_config:
            default_config["coloring"] = False
        if "enabled" not in default_config:
            default_config["enabled"] = True

        configs_by_stx["<default>"] = default_config

        for syntax, config in configs_by_stx.items():
            levels = range(len(config["rainbow_colors"]))
            config["keys"] = ["rb_l%d_%s" % (i, syntax) for i in levels]
            config["scopes"] = ["%s.l%d.rb" % (syntax, i) for i in levels]
            config["bad_key"] = "rb_mismatch_%s" % syntax
            config["bad_scope"] = "%s.mismatch.rb" % syntax

            pairs = config["bracket_pairs"]
            brackets = sorted(list(pairs.keys()) + list(pairs.values()))

            config["pattern"] = "|".join(re.escape(b) for b in brackets)
            config["selector"] = "|".join(config.pop("ignored_scopes"))

        cls.syntaxes_by_ext = syntaxes_by_ext
        cls.configs_by_stx = configs_by_stx
        cls.is_ready = True

    @classmethod
    def check_view_add_listener(cls, view, force=False):
        if not cls.is_ready:
            if force:
                msg = "SublimePlus: error in loading settings."
                sublime.error_message(msg)
            return

        if view.view_id in cls.view_listeners:
            return cls.view_listeners[view.view_id]

        if view.settings().get("rb_enable", True):
            syntax = cls.get_view_syntax(view) or "<default>"
            config = cls.configs_by_stx[syntax]
            if config["enabled"] or force:
                if config["bracket_pairs"]:
                    listener = RainbowBracketsViewListener(
                        view, syntax, config)
                    cls.view_listeners[view.view_id] = listener
                    return listener
                elif force:
                    sublime.error_message("empty brackets list")
        return None

    @classmethod
    def get_view_syntax(cls, view):
        if view is not None:
            syntax = view.syntax().name
            if syntax in cls.configs_by_stx:
                return syntax
            filename = view.file_name()
            if filename:
                ext = os.path.splitext(filename)[1]
                return cls.syntaxes_by_ext.get(ext, None)
        return None

    @classmethod
    def force_add_listener(cls, view):
        view.settings().set("rb_enable", True)
        return cls.check_view_add_listener(view, force=True)

    @classmethod
    def get_view_listener(cls, view):
        return cls.view_listeners.get(view.view_id, None)

    @classmethod
    def check_view_load_listener(cls, view):
        listener = cls.check_view_add_listener(view)
        if listener and not listener.bracket_regions_trees:
            listener.load()

    @classmethod
    def color_view(cls, view):
        listener = cls.get_view_listener(view)
        if listener and not listener.coloring:
            listener.coloring = True
            listener.check_bracket_regions()
        elif not listener:
            listener = cls.force_add_listener(view)
            if listener:
                listener.coloring = True
                listener.load()

    @classmethod
    def sweep_view(cls, view):
        listener = cls.get_view_listener(view)
        if listener and listener.coloring:
            listener.coloring = False
            listener.clear_bracket_regions()

    @classmethod
    def get_view_bracket_pairs(cls, view):
        listener = cls.get_view_listener(view)
        return listener and listener.brackets

    @classmethod
    def get_view_bracket_trees(cls, view):
        listener = cls.get_view_listener(view)
        if not listener:
            cls.setup_view_listener(view)
            listener = cls.get_view_listener(view)
        return listener and listener.bracket_regions_trees

    def on_load(self, view):
        if settings.get("rainbow_brackets_enabled"):
            self.check_view_load_listener(view)

    def on_post_save(self, view):
        if settings.get("rainbow_brackets_enabled"):
            self.check_view_load_listener(view)

    def on_activated(self, view):
        if settings.get("rainbow_brackets_enabled"):
            self.check_view_load_listener(view)

    def on_modified(self, view):
        if settings.get("rainbow_brackets_enabled"):
            listener = self.view_listeners.get(view.view_id, None)
            listener and listener.check_bracket_regions()

    def on_close(self, view):
        if settings.get("rainbow_brackets_enabled"):
            self.view_listeners.pop(view.view_id, None)


class ColorSchemeManager(sublime_plugin.EventListener):
    DEFAULT_CS = "Packages/Color Scheme - Default/Monokai.sublime-color-scheme"

    @classmethod
    def init(cls):
        def load_settings_build_cs():
            RainbowBracketsViewManager.load_config(cls.settings)
            cls.build_color_scheme()

        cls.prefs = sublime.load_settings("Preferences.sublime-settings")
        cls.settings = settings
        cls.prefs.add_on_change("color_scheme", cls.rebuild_color_scheme)
        cls.settings.add_on_change("default_config", load_settings_build_cs)
        cls.color_scheme = cls.prefs.get("color_scheme", cls.DEFAULT_CS)

        load_settings_build_cs()

    @classmethod
    def color_scheme_cache_path(cls):
        return os.path.join(sublime.packages_path(), "User", "Color Schemes", "RainbowBrackets")

    @classmethod
    def color_scheme_name(cls):
        return os.path.basename(
            cls.color_scheme).replace("tmTheme", "sublime-color-scheme")

    @classmethod
    def clear_color_schemes(cls, all=False):
        color_scheme_path = cls.color_scheme_cache_path()
        color_scheme_name = cls.color_scheme_name()
        for file in os.listdir(color_scheme_path):
            if file != color_scheme_name or all:
                try:
                    os.remove(os.path.join(color_scheme_path, file))
                except:
                    pass

    @classmethod
    def rebuild_color_scheme(cls):
        scheme = cls.prefs.get("color_scheme", cls.DEFAULT_CS)
        if scheme != cls.color_scheme:
            cls.color_scheme = scheme
            cls.build_color_scheme()

    @classmethod
    def build_color_scheme(cls):
        def nearest_color(color):
            b = int(color[5:7], 16)
            b += 1 - 2 * (b == 255)
            return color[:-2] + "%02x" % b

        def color_scheme_background(color_scheme):
            view = sublime.active_window().active_view()
            # origin_color_scheme = view.settings().get("color_scheme")
            view.settings().set("color_scheme", color_scheme)
            background = view.style().get("background")
            # view.settings().set("color_scheme", origin_color_scheme)
            return background

        background = color_scheme_background(cls.color_scheme)
        nearest_background = nearest_color(background)

        rules = []
        for value in RainbowBracketsViewManager.configs_by_stx.values():
            rules.append({
                "scope": value["bad_scope"],
                "foreground": value["mismatch_color"],
                "background": background
            })
            for scope, color in zip(value["scopes"], value["rainbow_colors"]):
                rules.append({
                    "scope": scope,
                    "foreground": color,
                    "background": nearest_background
                })
        color_scheme_data = {
            "name": os.path.splitext(os.path.basename(cls.color_scheme))[0],
            "author": "https://github.com/absop/RainbowBrackets",
            "variables": {},
            "globals": {},
            "rules": rules
        }

        color_scheme_path = cls.color_scheme_cache_path()
        color_scheme_name = cls.color_scheme_name()
        color_scheme_file = os.path.join(color_scheme_path, color_scheme_name)
        # We only need to write a same named color_scheme,
        # then sublime will load and apply it automatically.
        os.makedirs(color_scheme_path, exist_ok=True)
        with open(color_scheme_file, "w+") as file:
            file.write(json.dumps(color_scheme_data))


class AutoSaveEventListener(sublime_plugin.EventListener):

    def __init__(self):
        self.num_modifications = 0
        self.recently_saved = False

    def on_modified_async(self, view):
        self.num_modifications += 1
        filename = view.file_name()
        if self.recently_saved:
            pass
        elif settings.get("auto_save_on_modified") and filename and self.num_modifications >= settings.get("number_of_modifications_for_auto_save"):
            delay = settings.get("auto_save_delay_in_seconds")
            if settings.get("auto_save_only_included"):
                for path in settings.get("included_auto_save_files_field"):
                    if filename.endswith(path):
                        self.num_modifications = 0
                        sublime.set_timeout(
                            lambda: self.save_file(view), delay)
                        self.recently_saved = True
                        sublime.set_timeout(lambda: self.set_recent(), delay)
            else:
                for path in settings.get("ignore_auto_save_files_field"):
                    if filename.endswith(path):
                        return
                self.num_modifications = 0
                sublime.set_timeout(lambda: self.save_file(view), delay)
                self.recently_saved = True
                sublime.set_timeout(lambda: self.set_recent(), delay)

    def save_file(self, view):
        if view.is_dirty() and not view.is_loading() and not view.is_auto_complete_visible():
            view.run_command("save")
            sublime.status_message(' ')  # don't clog up status

    def set_recent(self):
        self.recently_saved = False


class AutoCloseEmptyGroup(sublime_plugin.EventListener):
    def on_pre_close(self, view):
        window = view.window()
        if window is None:
            return

        if view not in window.views():
            view.settings().set("auto_close_empty_group_is_tabless_view", True)

    def close_empty_group(self):
        window = sublime.active_window()
        for group in range(window.num_groups()):
            if len(window.views_in_group(group)) == 0:
                window.run_command("close_pane")
                return

    def on_close(self, view):
        if view.settings().get("auto_close_empty_group_is_tabless_view") is True:
            return
        self.close_empty_group()

    def on_post_move(self, view):
        self.close_empty_group()
