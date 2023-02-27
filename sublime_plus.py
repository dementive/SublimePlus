import sublime, sublime_plugin
import webbrowser, re, functools, os, zlib, subprocess, json, inspect, time, random
from itertools import tee, chain
from os.path import basename

# ------------------------------------------------------
# -                    Plugin Setup                    -
# ------------------------------------------------------

settings = None
notepad_toggle = False
fold_toggle = False
old_scheme = None
original_centered_setting = None
__storage_file__ = 'AutoFoldCode.sublime-settings'
__storage_path__ = os.path.join('Packages', 'User', __storage_file__)
CURRENT_STORAGE_VERSION = 1
MAX_BUFFER_SIZE_DEFAULT = 1000000
MAX_VIEWS = 20
MAX_WORDS_PER_VIEW = 150
MAX_FIX_TIME_SECS_PER_VIEW = 0.02

def plugin_loaded():
    global settings
    settings = sublime.load_settings("Sublime Plus.sublime-settings")
    for window in sublime.windows():
      for view in window.views():
        view.run_command("auto_fold_code_restore")
    build()


def build():
    global settings

    key_map = []

    default_replacements = settings.get('default_replacements', {})
    if(default_replacements == False):
        default_replacements = {}
    elif(type(default_replacements) is not dict):
        print('invalid default_replacements in settings')
        return

    default_triggers = settings.get('default_triggers', [])
    if(default_triggers == False):
        default_triggers = []
    elif(type(default_triggers) is not list):
        print('invalid default_triggers in settings')
        return

    custom_replacements = settings.get('custom_replacements', {})
    if(type(custom_replacements) is not dict):
        print('invalid custom_replacements in settings')
        return

    custom_triggers = settings.get('custom_triggers', [])
    if(type(custom_triggers) is not list):
        print('invalid custom_triggers in settings')
        return

    # Combine them
    default_replacements.update(custom_replacements)
    replacements = default_replacements
    triggers = list(set(default_triggers + custom_triggers))

    for mispelled in replacements:
        replacement = replacements[mispelled]

        for key in triggers:
            char = key
            if char == 'enter':
                char = '\n'

            # lowercase version
            entry = {'command': 'insert', 'args': {}}
            entry['args']['characters'] = replacement + char
            entry['keys'] = list(mispelled)
            entry['keys'].append(key)

            key_map.append(entry)

            entry = {'command': 'insert', 'args': {}}
            entry['args']['characters'] = (replacement + char).capitalize()
            entry['keys'] = list(mispelled.capitalize())
            entry['keys'].append(key)

            key_map.append(entry)


    if(not key_map):
        print('no key maps')
        return

    current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

    key_map_data = open('%s/Default.sublime-keymap' % current_dir, 'w')
    key_map_data.write(json.dumps(key_map))
    key_map_data.close()


# ------------------------------------------------------
# -                  Code Fold Methods                 -
# ------------------------------------------------------

def char_at(view, point):
    return view.substr(sublime.Region(point, point + 1))

def is_space(view, point):
    return char_at(view, point).isspace()

def is_newline(view, point):
    return char_at(view, point) == "\n"

# ------------------------------------------------------
# -                Comment Fold Methods                -
# ------------------------------------------------------

def previous_and_current(iterable, *iterables):
    prevs, items = tee(iterable, 2)
    prevs = chain([None], prevs)
    return zip(prevs, items, *iterables)

def is_comment_multi_line(view, region):
    return len(view.lines(region)) > 1

def is_comment_doc_block(view, region):
    region_str = view.substr(region)
    return region_str.rfind('/**') != -1

def normalize_comment(view, region):
    if is_comment_multi_line(view, region):
        return normalize_multiline_comment(view, region)
    else:
        return normalize_singleline_comment(view, region)

def normalize_singleline_comment(view, region):
    region_str = view.substr(region)
    last_newline = region_str.rfind('\n')

    if (last_newline == -1):
        return region
    else:
        return sublime.Region(region.begin(), region.begin() + last_newline)

def normalize_multiline_comment(view, region):
    lines = view.lines(region)
    last_line = lines[-1]
    last_point = last_line.b
    return sublime.Region(region.a, last_point)

# ------------------------------------------------------
# -                  Comment Methods                   -
# ------------------------------------------------------

def selections(view, default_to_all=True):
    regions = [r for r in view.sel() if not r.empty()]
    if not regions and default_to_all:
        regions = [sublime.Region(0, view.size())]
    return regions

# ------------------------------------------------------
# -                   Code Fold Class                  -
# ------------------------------------------------------

class CodeNodes:

    def __init__(self, view):
        self.regions = None # collection of Region objects
        self.view = view
        self.fold_regions = []
        self.find_code()

    def find_code(self):
        view = self.view
        self.regions = []
        regions = view.find_by_selector("-comment")
        for region in regions:
            a, b = region.begin(), region.end()
            # keep new line before the fold
            if is_newline(view, a):
                a += 1
            # keep the indent before next comment
            while is_space(view, b - 1):
                b -= 1
                if is_newline(view, b):
                    break
            # if it is still a valid fold, add it to the list
            if a < b:
                self.fold_regions.append(sublime.Region(a, b))

    def toggle_code_folding(self):
        global fold_toggle

        if not fold_toggle:
            self.code_fold()
            fold_toggle = True
        else:
            self.code_unfold()
            fold_toggle = False

    def code_fold(self):
        self.view.fold(self.fold_regions)

    def code_unfold(self):
        regions = self.view.find_by_selector("-comment")
        self.view.unfold(regions)

# ------------------------------------------------------
# -                 Comment Fold Class                 -
# ------------------------------------------------------

class CommentNodes:

    def __init__(self, view):
        self.comments = None # collection of Region objects
        self.settings = sublime.load_settings("Sublime Plus.sublime-settings")
        self.view = view
        self.find_comments()
        self.apply_settings()

    def find_comments(self):
        self.comments = [
            normalize_comment(self.view, c) for c in self.view.find_by_selector('comment')
        ]

    def apply_settings(self):
        if not self.settings.get('fold_single_line_comments'):
            self.remove_single_line_comments()

        if not self.settings.get('fold_multi_line_comments'):
            self.remove_multi_line_comments()

        if not self.settings.get('fold_doc_block_comments'):
            self.remove_doc_block_comments()

        if self.settings.get('concatenate_adjacent_comments'):
            self.concatenate_adjacent_comments()

    def remove_single_line_comments(self):
        self.comments = [c for c in self.comments if is_comment_multi_line(self.view, c) or is_comment_doc_block(self.view, c)]

    def remove_multi_line_comments(self):
        self.comments = [c for c in self.comments if not is_comment_multi_line(self.view, c) or is_comment_doc_block(self.view, c)]

    def remove_doc_block_comments(self):
        self.comments = [c for c in self.comments if not is_comment_doc_block(self.view, c)]

    def concatenate_adjacent_comments(self):
        """
        Merges any comments that are adjacent.
        """

        def concatenate(region1, region2):
            return region1.cover(region2)

        def is_adjacent(region1, region2):
            region_inbetween = sublime.Region(region1.end(), region2.begin())
            return len(self.view.substr(region_inbetween).strip()) == 0

        concatenated_comments = []

        for prev_comment, comment in previous_and_current(self.comments):
            concatenated_comment = None

            # prev wont be set on first iteration
            if prev_comment and is_adjacent(prev_comment, comment):
                concatenated_comment = concatenate(concatenated_comments.pop(), comment)

            concatenated_comments.append(concatenated_comment or comment)

        self.comments = concatenated_comments

    def fold(self):
        self.view.fold(self.comments)

    def unfold(self):
        self.view.unfold(self.comments)

    def toggle_folding(self):
        def is_folded(comments):
            return self.view.unfold(self.comments)  # False if /already folded/

        self.unfold() if is_folded(self.comments) else self.fold()

# ------------------------------------------------------
# -                      Commands                      -
# ------------------------------------------------------


# *************************************************
# *                 Comment Header                *
# *************************************************

class CommentHeaderCommand(sublime_plugin.TextCommand):
    ROW_LENGTH = 50

    def run(self, edit):
        symbol = settings.get("comment_format")
        for region in self.view.sel():
            bannerText = self.view.substr(region)
            if bannerText:
                self.view.erase(edit, region)
                self.view.insert(edit, region.begin(),
                                 self.full_screen_banner(bannerText,symbol))
                region_len = (region.begin() +
                              self.ROW_LENGTH*(2+len(self.lines)))
                self.view \
                    .selection \
                    .add(sublime.Region(region.begin(), region_len))
        # add the language dependend comment characters
        self.view.run_command("toggle_comment", False)

        # remove the selection of the cursor
        self.view.run_command("move", {"by": "characters", "forward": True})

    def full_screen_banner(self, string, symbol):
        def outer_row():
            return (self.ROW_LENGTH - 1) * symbol + '\n'

        def inner_row():
            result = ""
            self.lines = string.splitlines()
            # textwrap.wrap(string)

            # center each line
            for line in self.lines:
                result += "{2} {0:^{1}}{2}\n".format(line, self.ROW_LENGTH-4,
                                                     symbol)
            return result
        return outer_row() + inner_row() + outer_row()

class CommentHeaderTwoCommand(sublime_plugin.TextCommand):

    ROW_LENGTH_TWO = 35

    def run(self, edit):
        symbol_two = settings.get("comment_format_two")
        for region in self.view.sel():
            bannerText = self.view.substr(region)
            if bannerText:
                self.view.erase(edit, region)
                self.view.insert(edit, region.begin(),
                                 self.full_screen_banner(bannerText,symbol_two))
                region_len = (region.begin() +
                              self.ROW_LENGTH_TWO*(2+len(self.lines)))
                self.view \
                    .selection \
                    .add(sublime.Region(region.begin(), region_len))
        # add the language dependend comment characters
        self.view.run_command("toggle_comment", False)

        # remove the selection of the cursor
        self.view.run_command("move", {"by": "characters", "forward": True})

    def full_screen_banner(self, string, symbol_two):
        def outer_row():
            return (self.ROW_LENGTH_TWO - 1) * symbol_two + '\n'

        def inner_row():
            result = ""
            self.lines = string.splitlines()
            # textwrap.wrap(string)

            # center each line
            for line in self.lines:
                result += "{2} {0:^{1}}{2}\n".format(line, self.ROW_LENGTH_TWO-4,
                                                     symbol_two)
            return result
        return outer_row() + inner_row() + outer_row()


# *************************************************
# *                NotePad Commands               *
# *************************************************


class NotePadMakeCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        global old_scheme
        window = sublime.active_window()
        view = window.active_view()

        if window.is_menu_visible() == True:
            window.set_menu_visible(False)
        window.set_sidebar_visible(False)
        if not settings.get("show_tabs_in_notepad"):
            window.set_tabs_visible(False)
        if not settings.get("show_status_bar_in_notepad"):
            window.set_status_bar_visible(False)
        if not settings.get("show_minimap_in_notepad"):
            window.set_minimap_visible(False)

        if not settings.get("show_gutter_in_notepad"):
            view.settings().set('gutter',False)
        view.settings().set("toggle_status_bar",False)
        window.run_command('hide_panel')
        old_scheme = view.settings().get("color_scheme")
        original_centered_setting = view.settings().get("draw_centered")
        if settings.get("notepad_color_scheme_mode") == "Light":
            view.settings().set("color_scheme", "NotepadLight.hidden-color-scheme")
        elif settings.get("notepad_color_scheme_mode") == "Dark":
            view.settings().set("color_scheme", "Notepad.hidden-color-scheme")
        if settings.get("draw_centered_notepad"):
            view.settings().set("draw_centered",True)

class NotePadNewCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        sublime.run_command("new_window")
        sublime.run_command('note_pad_make')

class ToggleNotePadCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        global notepad_toggle
        global old_scheme
        global original_centered_setting

        window = sublime.active_window()
        view = window.active_view()

        if not notepad_toggle:
            sublime.run_command('note_pad_make')
            notepad_toggle = True
        else:
            window.set_tabs_visible(True)
            window.set_status_bar_visible(True)
            window.set_minimap_visible(True)
            view.settings().set("gutter",True)
            view.settings().set("toggle_status_bar",True)
            if settings.get("notepad_color_scheme_mode") != "Default":
                view.settings().set("color_scheme", old_scheme)
            if settings.get("draw_centered_notepad"):
                # If draw_centered was already on, turn it back on. Else turn it off
                if original_centered_setting:
                    view.settings().set("draw_centered",True)
                else:
                    view.settings().set("draw_centered",False)
            notepad_toggle = False


# def save_output_panel_contents():
#     window = sublime.active_window()
#     if window.find_output_panel("NotePad") == None:
#         return 1
#     view = window.find_output_panel("NotePad")
#     region = sublime.Region(0, len(self.view))
#     string = view.substr(region)
#     print(string)

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
            view.settings().set('gutter',False)
        if settings.get("draw_centered_temp_notepad"):
            view.settings().set("draw_centered",True)
        self.shown = True

    def run(self):
        window = sublime.active_window()
        if window.find_output_panel("NotePad") == None:
            panel = window.create_output_panel("NotePad")
            window.run_command("show_panel", {"panel": "output.NotePad"})
            self.panel_creation(window, panel)
        #elif self.shown:
            #window.destroy_output_panel("NotePad")
            #save_output_panel_contents()
            #self.shown = False
        else:
            window.run_command("show_panel", {"panel": "output.NotePad"})
            view = window.find_output_panel("NotePad")
            self.panel_creation(window, view)

# *************************************************
# *                Folding Commands               *
# *************************************************

class GenToggleFoldSelectionCommand(sublime_plugin.TextCommand):
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
                sublime.set_timeout(lambda: sublime.status_message( 'There is no text selected!'), 0)


class ToggleFoldEverythingCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        region = sublime.Region(0, len(self.view))
        def is_folded(region):
            return self.view.unfold(region)

        if not is_folded(region):
            self.view.fold(region)
        else:
            self.view.unfold(region)

class ToggleCodeFoldCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        code = CodeNodes(self.view)
        code.toggle_code_folding()

class CodeFoldCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        code = CodeNodes(self.view)
        code.code_fold()

class CodeUnfoldCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        code = CodeNodes(self.view)
        code.code_unfold()

class ToggleFoldCommentsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        comments = CommentNodes(self.view)
        comments.toggle_folding()

class FoldCommentsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        comments = CommentNodes(self.view)
        comments.fold()

class UnfoldCommentsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        comments = CommentNodes(self.view)
        comments.unfold()

class SplitSelectionCommand(sublime_plugin.TextCommand):

  def run(self, edit, separator = None):

    self.savedSelection = [r for r in self.view.sel()]

    selectionSize = sum(map(lambda region: region.size(), self.savedSelection))
    if selectionSize == 0:
      # nothing to do
      sublime.status_message("Cannot split an empty selection.")
      return

    if separator != None:
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

class CycleThroughRegionsCommand(sublime_plugin.TextCommand):

  def run(self, edit):

    view = self.view
    visibleRegion = view.visible_region()
    selectedRegions = view.sel()

    nextRegion = None

    for region in selectedRegions:
      str_buffer = view.substr(region)
      if len(str_buffer) == 0:
        sublime.set_timeout(lambda: sublime.status_message( 'There is no text selected!'), 0)
      if region.end() > visibleRegion.b:
        nextRegion = region
        break

    if nextRegion is None:
      nextRegion = selectedRegions[0]

    view.show(nextRegion, False)

# **********************************
# *         Basic Movement         *
# **********************************

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

# **********************************
# *          Fast Movement         *
# **********************************

class FastMoveCommand(sublime_plugin.TextCommand):
    def run(self, edit, direction, extend=False):
        window = sublime.active_window()
        if (direction == "up"):
            for i in range(settings.get("fast_move_horizontal_character_amount")):
                window.run_command("move", {"by": "lines", "forward": False, "extend": extend})
        if (direction == "down"):
            for i in range(settings.get("fast_move_horizontal_character_amount")):
                window.run_command("move", {"by": "lines", "forward": True, "extend": extend})
        if (direction == "left"):
            for i in range(settings.get("fast_move_horizontal_character_amount")):
                window.run_command("move", {"by": "characters", "forward": False, "extend": extend})
        if (direction == "right"):
            for i in range(settings.get("fast_move_horizontal_character_amount")):
                window.run_command("move", {"by": "characters", "forward": True, "extend": extend})

class RenameFileInTabCommand(sublime_plugin.TextCommand):
    def run (self, edit, args=None, index=-1, group=-1, **kwargs):
        w = self.view.window()
        views = w.views_in_group(group)
        view = views[index]

        full_path = view.file_name()
        if full_path is None:
            return

        directory, fn = os.path.split(full_path)
        v = w.show_input_panel("New file name:",
            fn,
            functools.partial(self.on_done, full_path, directory),
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
        sublime.set_timeout(lambda: sublime.status_message('Selected file cannot be opened in Terminal.'), 0)
  def is_enabled(self):
    if sublime.platform() == "windows":
      return True
    else: return False
  def is_visible(self):
    if sublime.platform() == "windows":
      return True
    else: return False

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
        sublime.set_timeout(lambda: sublime.status_message('Selected file cannot be deleted.'), 0)

class SearchOnlineInputHandler(sublime_plugin.TextInputHandler):

    def __init__(self, stype):
        self.stype = stype

    def name(self):
        return 'url'


    def placeholder(self):
        if self.stype == "search":
            return ""
        else:
            return "Open Url"

class SearchOnlineCommand(sublime_plugin.TextCommand):

    def input_description(self):
        return "Search Online"

    def input(self, args):
        if 'url' not in args:
            stype = args.get("stype")
            return SearchOnlineInputHandler(stype)

    def run(self, edit, url, stype):
        if stype == "search":
            webbrowser.open_new_tab('http://www.google.com/search?btnG=1&q=%s' % url)
        elif stype == "url":
            webbrowser.open_new_tab(url)


class WebsiteInputHandler(sublime_plugin.ListInputHandler):

    def __init__(self): self.site_dict = settings.get('favorite_website_list')

    def name(self):
        return 'website'

    def list_items(self):
        keys = []
        for x in self.site_dict: keys.append(x)
        return keys

    def preview(self, value):
        return self.site_dict[value]

class SelectFavoriteWebsiteCommand(sublime_plugin.TextCommand):

    def input_description(self):
        return "Select Website"

    def input(self, args):
        if 'website' not in args:
            return WebsiteInputHandler()

    def run(self, edit, website):
        site_dict = settings.get('favorite_website_list')
        webbrowser.open_new_tab(site_dict[website])

class WorkspaceListInputHandler(sublime_plugin.ListInputHandler):

    def __init__(self):
        self.project_directories = settings.get('sublime_workspace_directories_list')

    def find_workspaces(self):
        s_workspace_file = re.compile("^.*?\.sublime-workspace$")
        results = []
        for directory in self.project_directories:
            for name in os.listdir(directory):
                if s_workspace_file.match(name):
                    results.append(name)
        return results

    def name(self):
        return 'workspace'

    def list_items(self):
        list_items = []
        for workspace in self.find_workspaces():
            workspace = workspace.replace(".sublime-workspace", "")
            list_items.append(workspace)
        return list_items

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
        if workspace != None:
            workspace = workspace + ".sublime-workspace"
            project_directories = settings.get('sublime_workspace_directories_list')
            if len(project_directories) > 0:
                #space_path = os.path.abspath(workspace)
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
            sublime.set_timeout(lambda: sublime.status_message( 'No directories have been added to the workspace directories list. See Sublime Plus.sublime-setting for more info.'), 0)


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
                'additive': idx > 0 or kwargs.get('additive', False) # if there are multiple selections, act like pressing Ctrl while double clicking - otherwise we will end up with only one selection. The first double click should replace any existing selections unless told otherwise.
            })


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


# Listen to changes in views to automatically save code folds.
class AutoFoldCodeListener(sublime_plugin.EventListener):
  def on_load_async(self, view):
    view.run_command("auto_fold_code_restore")

  def on_post_save_async(self, view):
    # Keep only the latest version, since it's guaranteed that on open, the
    # saved version of the file is opened.
    if settings.get("save_folds_on_save"):
        _save_view_data(view, True)

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
    _save_view_data(view, False)

  def on_text_command(self, view, command_name, args):
    if command_name == 'unfold_all' and view.file_name() != None:
      _clear_cache(view.file_name())

# ------------------- #
#   Window Commands   #
# ------------------- #

# Clears all the saved code folds and unfolds all the currently open windows.
class AutoFoldCodeClearAllCommand(sublime_plugin.WindowCommand):
  def run(self):
    _clear_cache('*')
    self.window.run_command('auto_fold_code_unfold_all')

# Clears the cache for the current view, and unfolds all its regions.
class AutoFoldCodeClearCurrentCommand(sublime_plugin.WindowCommand):
  def run(self):
    view = self.window.active_view()
    if view and view.file_name():
      view.unfold(sublime.Region(0, view.size()))
      _clear_cache(view.file_name())

  def is_enabled(self):
    view = self.window.active_view()
    return view != None and view.file_name() != None

# Unfold all code folds in all open files.
class AutoFoldCodeUnfoldAllCommand(sublime_plugin.WindowCommand):
  def run(self):
    for window in sublime.windows():
      for view in window.views():
        view.unfold(sublime.Region(0, view.size()))

# ----------------- #
#   Text Commands   #
# ----------------- #

class AutoFoldCodeRestoreCommand(sublime_plugin.TextCommand):
  def run(self, edit):
    file_name = self.view.file_name()
    if file_name == None:
      return

    # Skip restoring folds if the file size is larger than `max_buffer_size`.
    settings = _load_storage_settings(save_on_reset=True)
    if self.view.size() > settings.get("max_buffer_size", MAX_BUFFER_SIZE_DEFAULT):
      return

    view_content_checksum = _compute_view_content_checksum(self.view)

    # Restore folds
    view_folds_data = settings.get("folds").get(file_name, {})
    for a, b in view_folds_data.get(view_content_checksum, []):
      self.view.fold(sublime.Region(a, b))

    # Restore selections
    if settings.get("save_selections") == True:
      view_selection_data = settings.get("selections").get(file_name, {})
      self.view.selection.clear()
      for a, b in view_selection_data.get(view_content_checksum, []):
        self.view.selection.add(sublime.Region(a, b))

# ----------- #
#   Helpers   #
# ----------- #

# Save the folded regions of the view to disk.
def _save_view_data(view, clean_existing_versions):
  file_name = view.file_name()
  if file_name == None:
    return

  # Skip saving data if the file size is larger than `max_buffer_size`.
  settings = _load_storage_settings(save_on_reset=False)
  if view.size() > settings.get("max_buffer_size", MAX_BUFFER_SIZE_DEFAULT):
    return

  def _save_region_data(data_key, regions):
    all_data = settings.get(data_key)
    if regions:
      if clean_existing_versions or not file_name in all_data:
        all_data[file_name] = {}

      view_data = all_data.get(file_name)
      view_data[view_content_checksum] = regions
    else:
      all_data.pop(file_name, None)

    settings.set(data_key, all_data)

  view_content_checksum = _compute_view_content_checksum(view)

  # Save folds
  fold_regions = [(r.a, r.b) for r in view.folded_regions()]
  _save_region_data("folds", fold_regions)

  # Save selections if set
  if settings.get("save_selections") == True:
    selection_regions = [(r.a, r.b) for r in view.selection]
    _save_region_data("selections", selection_regions)

  # Save settings
  sublime.save_settings(__storage_file__)

# Clears the cache. If name is '*', it will clear the whole cache.
# Otherwise, pass in the file_name of the view to clear the view's cache.
def _clear_cache(name):
  settings = _load_storage_settings(save_on_reset=False)

  def _clear_cache_section(data_key):
    all_data = settings.get(data_key)
    file_names_to_delete = [file_name for file_name in all_data if name == '*' or file_name == name]
    for file_name in file_names_to_delete:
      all_data.pop(file_name)
    settings.set(data_key, all_data)

  _clear_cache_section("folds")
  _clear_cache_section("selections")
  sublime.save_settings(__storage_file__)

# Loads the settings, resetting the storage file, if the version is old (or broken).
# Returns the settings instance
def _load_storage_settings(save_on_reset):
  try:
    settings = sublime.load_settings(__storage_file__)
  except Exception as e:
    print('[AutoFoldCode.] Error loading settings file (file will be reset): ', e)
    save_on_reset = True

  if _is_old_storage_version(settings):
    settings.set("max_buffer_size", MAX_BUFFER_SIZE_DEFAULT)
    settings.set("version", CURRENT_STORAGE_VERSION)
    settings.set("folds", {})
    settings.set("selections", {})

    if save_on_reset:
      sublime.save_settings(__storage_file__)

  return settings

def _is_old_storage_version(settings):
  settings_version = settings.get("version", 0)

  # Consider the edge case of a file named "version".
  return not isinstance(settings_version, int) or settings_version < CURRENT_STORAGE_VERSION

# Returns the checksum in Python hex string format.
#
# The view content returned is always the latest version, even when closing
# without saving.
def _compute_view_content_checksum(view):
  view_content = view.substr(sublime.Region(0, view.size()))
  int_crc32 = zlib.crc32(view_content.encode('utf-8'))
  return hex(int_crc32 % (1<<32))



# ----------------------------------
# -            AutoSave            -
# ----------------------------------

num_modifications = 0
recently_saved = False

class AutoSaveEventListener(sublime_plugin.EventListener):

    def on_modified_async(self, view):
        global num_modifications
        global recently_saved
        num_modifications += 1
        filename = view.file_name()
        if recently_saved:
            pass
        elif settings.get("auto_save_on_modified") and filename and num_modifications >= settings.get("number_of_modifications_for_auto_save"):
            delay = settings.get("auto_save_delay_in_seconds")
            if settings.get("auto_save_only_included"):
                for path in settings.get("included_auto_save_files_field"):
                    if filename.endswith(path):
                        num_modifications = 0
                        sublime.set_timeout(lambda: self.save_file(view), delay)
                        recently_saved = True
                        sublime.set_timeout(lambda: self.set_recent(), delay)
            else:
                for path in settings.get("ignore_auto_save_files_field"):
                    if filename.endswith(path):
                        return
                num_modifications = 0
                sublime.set_timeout(lambda: self.save_file(view), delay)
                recently_saved = True
                sublime.set_timeout(lambda: self.set_recent(), delay)

    def save_file(self, view):
        if view.is_dirty() and not view.is_loading() and not view.is_auto_complete_visible():
            view.run_command("save")
            sublime.status_message(' ') #don't clog up status

    def set_recent(self):
        global recently_saved
        recently_saved = False

class SelectionToSnippetCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        selection = view.sel()
        str_out = ""

        for region in selection:
            str_buffer = view.substr(region)
            if len(str_buffer) == 0:
                sublime.set_timeout(lambda: sublime.status_message( 'There is no text selected!'), 0)
            else:
                str_out = str_out + "\n" + str_buffer

        window = sublime.active_window()
        window.run_command('new_file')
        snippet_view = window.active_view()
        snippet_view.set_name("snippet.sublime-snippet")
        snippet_view.run_command("insert_snippet_contents", {'string': str_out})


class InsertSnippetContentsCommand(sublime_plugin.TextCommand):
    def run(self, edit, string):
        snippet_head = "<snippet>\n\t<content><![CDATA["
        snippet_foot = "\n\t]]></content>\n\t<!-- ${1:Selection Field 1}.${2:Selection Field 2} -->\n\t<tabTrigger>add_centralization</tabTrigger>\n\t<scope>source.python</scope>\n\t<description>Description</description>\n</snippet>"                       
        string = snippet_head + string + snippet_foot
        self.view.insert(edit, len(self.view), string)



# ----------------------------------
# -          Autocomplete          -
# ----------------------------------

class AllAutocomplete(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):
        if is_excluded(view.scope_name(locations[0]), settings.get("exclude_from_completion", [])):
            return []

        words = []

        # Limit number of views but always include the active view. This
        # view goes first to prioritize matches close to cursor position.
        other_views = [
            v
            for v in sublime.active_window().views()
            if v.id != view.id and not is_excluded(v.scope_name(0), settings.get("exclude_sources", []))
        ]
        views = [view] + other_views
        views = views[0:MAX_VIEWS]

        for v in views:
            if len(locations) > 0 and v.id == view.id:
                view_words = v.extract_completions(prefix, locations[0])
            else:
                view_words = v.extract_completions(prefix)
            view_words = filter_words(view_words)
            view_words = fix_truncation(v, view_words)
            words += [(w, v) for w in view_words]

        words = without_duplicates(words)

        matches = []
        for w, v in words:
            trigger = w
            contents = w.replace('$', '\\$')
            if v.id != view.id and v.file_name():
                trigger += '\t(%s)' % basename(v.file_name())
            if v.id == view.id:
                trigger += '\tabc'
            matches.append((trigger, contents))
        return matches

def is_excluded(scope, excluded_scopes):
    for excluded_scope in excluded_scopes:
        if excluded_scope in scope:
            return True
    return False

def filter_words(words):
    MIN_WORD_SIZE = settings.get("min_word_size", 3)
    MAX_WORD_SIZE = settings.get("max_word_size", 50)
    return [w for w in words if MIN_WORD_SIZE <= len(w) <= MAX_WORD_SIZE][0:MAX_WORDS_PER_VIEW]


# keeps first instance of every word and retains the original order, O(n)
def without_duplicates(words):
    result = []
    used_words = set()
    for w, v in words:
        if w not in used_words:
            used_words.add(w)
            result.append((w, v))
    return result


# Ugly workaround for truncation bug in Sublime when using view.extract_completions()
# in some types of files.
def fix_truncation(view, words):
    fixed_words = []
    start_time = time.time()

    for i, w in enumerate(words):
        #The word is truncated if and only if it cannot be found with a word boundary before and after

        # this fails to match strings with trailing non-alpha chars, like
        # 'foo?' or 'bar!', which are common for instance in Ruby.
        match = view.find(r'\b' + re.escape(w) + r'\b', 0)
        truncated = is_empty_match(match)
        if truncated:
            #Truncation is always by a single character, so we extend the word by one word character before a word boundary
            extended_words = []
            view.find_all(r'\b' + re.escape(w) + r'\w\b', 0, "$0", extended_words)
            if len(extended_words) > 0:
                fixed_words += extended_words
            else:
                # to compensate for the missing match problem mentioned above, just
                # use the old word if we didn't find any extended matches
                fixed_words.append(w)
        else:
            #Pass through non-truncated words
            fixed_words.append(w)

        # if too much time is spent in here, bail out,
        # and don't bother fixing the remaining words
        if time.time() - start_time > MAX_FIX_TIME_SECS_PER_VIEW:
            return fixed_words + words[i+1:]

    return fixed_words


if sublime.version() >= '3000':
    def is_empty_match(match):
        return match.empty()
else:
    plugin_loaded()
    def is_empty_match(match):
        return match is None


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

class UnderlineSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        # TODO turn into a toggle
        selection = self.view.sel()
        num = random.random()
        for region in selection:
            str_buffer = self.view.substr(region)
            if len(str_buffer) == 0:
                sublime.set_timeout(lambda: sublime.status_message( 'There is no text selected!'), 0)
            else:
                regions = [region]
                self.view.add_regions(str_buffer + str(num), regions, "region.redish", "", sublime.HIDE_ON_MINIMAP | sublime.PERSISTENT | sublime.DRAW_SOLID_UNDERLINE | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE )
                #self.view.add_regions("mark", regions, "mark", "dot", sublime.HIDDEN | sublime.PERSISTENT)

class UnderscoreToSpaceCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        # Changes all underscores in current selections to spaces
        selection = self.view.sel()
        for region in selection:
            string = self.view.substr(region).replace("_", " ").replace("-", " ")
            self.view.erase(edit, region)
            self.view.insert(edit, region.a, string)

class UnderscoreToTitleCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        selection = self.view.sel()
        for region in selection:
            string = self.view.substr(region).replace("_", " ").title()
            self.view.erase(edit, region)
            self.view.insert(edit, region.a, string)