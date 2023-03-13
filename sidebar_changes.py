import sublime
import sublime_plugin
import threading
import subprocess
import os
import shutil
from functools import partial
from collections import defaultdict


change_count_trigger = 0

def plugin_loaded():
    global close_sidebar_if_opened
    global change_count_trigger
    global settings
    global settings_base

    settings = sublime.load_settings("Sublime Plus.sublime-settings")
    settings_base = sublime.load_settings("Preferences.sublime-settings")
    plugin_reload()
    settings.add_on_change('reload', plugin_reload)
    settings_base.add_on_change('focusfileonsidebar-reload', plugin_reload)
    change_count_trigger = settings.get("change_count_sidebar_auto_close")


def plugin_reload():
    global close_sidebar_if_opened
    close_sidebar_if_opened = settings_base.get(
        'close_sidebar_if_opened', settings.get('close_sidebar_if_opened'))


def plugin_unloaded():
    settings.clear_on_change('reload')
    settings_base.clear_on_change('focusfileonsidebar-reload')


def refresh_folders(self):
    data = get_project_json(self)
    set_project_json(self, {})
    set_project_json(self, data)


def get_project_json(self):
    return self.window.project_data()


def set_project_json(self, data):
    return self.window.set_project_data(data)


def reveal_and_focus_in_sidebar(self):
    self.window.run_command("reveal_in_side_bar")
    self.window.run_command('move', {'by': 'lines', 'forward': True})
    self.window.run_command('move', {'by': 'lines', 'forward': False})
    self.window.run_command("focus_side_bar")


class FocusFileOnSidebar(sublime_plugin.WindowCommand):
    def run(self):
        if not self.window.is_sidebar_visible():
            refresh_folders(self)
            self.window.set_sidebar_visible(True)
            # set_project_data is asynchronous so we need settimeout for subsequent commands
            sublime.set_timeout_async(lambda: reveal_and_focus_in_sidebar(self), 250)
        else:
            if close_sidebar_if_opened:
                self.window.set_sidebar_visible(False)
                refresh_folders(self)
            else:
                refresh_folders(self)
                sublime.set_timeout_async(lambda: reveal_and_focus_in_sidebar(self), 250)


class Vars:
    auto_hide = True


class ToggleHideSidebarCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        Vars.auto_hide = not Vars.auto_hide
        sublime.active_window().set_sidebar_visible(not Vars.auto_hide)


class HideSidebarWhenNotFocussedListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        try:
            if view and Vars.auto_hide:
                if len(view.window().views()) == 0:
                    # no open views, so show sidebar
                    if settings.get('show_sidebar_when_no_open_views'):
                        view.window().set_sidebar_visible(True)
                elif view.window().is_sidebar_visible():
                    # sidebar is visible, so hide it
                    if settings.get('hide_side_bar_when_not_focused'):
                        view.window().set_sidebar_visible(False)
        except AttributeError:
            sublime.set_timeout(lambda: sublime.status_message(''), 0)


class SidebarHoverToggleListener(sublime_plugin.EventListener):

    def __init__(self):
        self.hovering_over_sidebar = False

    def on_hover(self, view, point, hover_zone):
        if not settings.get('sidebar_toggle_on_hover', False):
            return

        if hover_zone == sublime.HOVER_GUTTER:
            sublime.set_timeout(lambda: self.open_wait(view, hover_zone), settings.get('sidebar_hover_open_time'))

        else:
            if not settings.get('sidebar_toggle_auto_hide', True):
                return
            if self.hovering_over_sidebar:
                sublime.set_timeout(lambda: self.close_wait(view, hover_zone), settings.get('sidebar_hover_close_time'))

    def open_wait(self, view, hover_zone):
        if hover_zone != sublime.HOVER_GUTTER:
            return
        if not view.window().is_sidebar_visible() and not view.is_popup_visible():
            if settings.get('sidebar_hover_open_mode') == "open":
                view.window().run_command("toggle_side_bar")
            if settings.get('sidebar_hover_open_mode') == "open_and_focus":
                view.window().run_command("focus_file_on_sidebar")

            self.hovering_over_sidebar = True

    def close_wait(self, view, hover_zone):
        if hover_zone == sublime.HOVER_GUTTER:
            return
        if view.window().is_sidebar_visible():
            self.hovering_over_sidebar = False
            view.window().run_command("toggle_side_bar")


class AutoHideSidebarListener(sublime_plugin.EventListener):

    def __init__(self):
        self.change_counter = defaultdict(int)

    def on_modified_async(self, view):
        if settings.get("close_sidebar_after_changes"):
            if view.window() and len(view.window().folders()) > 0:
                if is_sidebar_visible(view.window()):
                    if view.settings().get("is_widget"):
                        return
                    count = increment_change_count(view.window().id())
                    if count >= change_count_trigger:
                        self.hide_sidebar(view)

    def hide_sidebar(self, view):
        if is_sidebar_visible(view.window()):
            if view.window():
                view.window().set_sidebar_visible(False)

    def increment_change_count(id):
        self.change_counter[id] += 1
        return self.change_counter[id]


class FileopRevealInSideBar(sublime_plugin.TextCommand):
    def run(self, edit, args=None, index=-1, group=-1, **kwargs):
        w = self.view.window()
        views = w.views_in_group(group)
        view = views[index]

        w.focus_view(view)
        w.run_command('reveal_in_side_bar')


class SideBarCommand(sublime_plugin.WindowCommand):
    def copy_to_clipboard(self, data):
        sublime.set_clipboard(data)
        lines = len(data.split('\n'))
        self.window.status_message('Copied {} to clipboard'.format(
            '{} lines'.format(lines) if lines > 1 else '"{}"'.format(data)
        ))

    def get_path(self, paths):
        try:
            return paths[0]
        except IndexError:
            return self.window.active_view().file_name()

    @staticmethod
    def retarget_view(source, destination):
        source = os.path.normcase(os.path.abspath(source))
        destination = os.path.normcase(os.path.abspath(destination))
        for window in sublime.windows():
            for view in window.views():
                path = os.path.abspath(view.file_name())
                if os.path.normcase(path) == source:
                    view.retarget(destination)

    @staticmethod
    def retarget_all_views(source, destination):
        if source[-1] != os.path.sep:
            source += os.path.sep

        if destination[-1] != os.path.sep:
            destination += os.path.sep

        for window in sublime.windows():
            for view in window.views():
                filename = view.file_name()
                if os.path.commonprefix([source, filename]) == source:
                    view.retarget(os.path.join(destination, filename[len(source):]))


class MultipleFilesMixin(object):
    def get_paths(self, paths):
        return paths or [self.get_path(paths)]


class SideBarMenuCopyNameCommand(MultipleFilesMixin, SideBarCommand):
    def run(self, paths):
        leafs = (os.path.split(path)[1] for path in self.get_paths(paths))
        self.copy_to_clipboard('\n'.join(leafs))

    def description(self):
        return 'Copy Filename'


class SideBarMenuCopyRelativePathCommand(MultipleFilesMixin, SideBarCommand):
    def run(self, paths):
        paths = self.get_paths(paths)
        root_paths = self.window.folders()
        relative_paths = []

        for path in paths:
            if not root_paths:
                relative_paths.append(os.path.basename(path))
            else:
                for root in root_paths:
                    if path.startswith(root):
                        p = os.path.relpath(path, root)
                        relative_paths.append(p)
                        break

        if not relative_paths:
            relative_paths.append(os.path.basename(path))

        self.copy_to_clipboard('\n'.join(relative_paths))

    def description(self):
        return 'Copy Relative Path'


class SideBarTerminalCommand(MultipleFilesMixin, SideBarCommand):
    def run(self, paths):
        paths = self.get_paths(paths)
        env = os.environ.copy()
        if os.path.isdir(paths[0]):
            subprocess.Popen("cmd.exe", env=env, cwd=paths[0])
        else:
            file = paths[0]
            res_str = file[file.rfind("\\"):len(file)]
            file = file.replace(res_str, "")
            subprocess.Popen("cmd.exe", env=env, cwd=file)

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


class SideBarMenuCopyAbsolutePathCommand(MultipleFilesMixin, SideBarCommand):
    def run(self, paths):
        paths = self.get_paths(paths)
        self.copy_to_clipboard('\n'.join(paths))

    def description(self):
        return 'Copy Absolute Path'


class SideBarMenuDuplicateCommand(SideBarCommand):
    def run(self, paths=[]):
        source = self.get_path(paths)
        base, leaf = os.path.split(source)

        name, ext = os.path.splitext(leaf)
        if ext != '':
            while '.' in name:
                name, _ext = os.path.splitext(name)
                ext = _ext + ext
                if _ext == '':
                    break

        input_panel = self.window.show_input_panel('Duplicate as:', source, partial(self.on_done, source, base), None, None)
        input_panel.sel().clear()
        input_panel.sel().add(sublime.Region(len(base) + 1, len(source) - len(ext)))

    def on_done(self, source, base, new):
        new = os.path.join(base, new)
        threading.Thread(target=self.copy, args=(source, new)).start()

    def copy(self, source, new):
        self.window.status_message('Copying "{}" to "{}"'.format(source, new))

        try:
            base = os.path.dirname(new)
            if not os.path.exists(base):
                os.makedirs(base)

            if os.path.isdir(source):
                shutil.copytree(source, new)
            else:
                shutil.copy2(source, new)
                self.window.open_file(new)

        except OSError as error:
            self.window.status_message('Unable to duplicate: "{}" to "{}". {error}'.format(source, new, error))
        except:
            self.window.status_message('Unable to duplicate: "{}" to "{}"'.format(source, new))

        self.window.run_command('refresh_folder_list')

    def description(self):
        return 'Duplicate…'


class SideBarMenuMoveCommand(SideBarCommand):
    def run(self, paths):
        source = self.get_path(paths)
        base, leaf = os.path.split(source)
        _, ext = os.path.splitext(leaf)

        input_panel = self.window.show_input_panel('Move to:', source, partial(self.on_done, source), None, None)
        input_panel.sel().clear()
        input_panel.sel().add(sublime.Region(len(base) + 1, len(source) - len(ext)))

    def on_done(self, source, new):
        threading.Thread(target=self.move, args=(source, new)).start()

    def move(self, source, new):
        self.window.status_message('Moving "{}" to "{}"'.format(source, new))

        try:
            base = os.path.dirname(new)
            if not os.path.exists(base):
                os.makedirs(base)

            shutil.move(source, new)

            if os.path.isfile(new):
                self.retarget_view(source, new)
            else:
                self.retarget_all_views(source, new)

        except OSError as error:
            self.window.status_message('Unable to moving: "{}" to "{}". {}'.format(source, new, error))
        except:
            self.window.status_message('Unable to moving: "{}" to "{}"'.format(source, new))

        self.window.run_command('refresh_folder_list')

    def description(self):
        return 'Move…'


class SideBarMenuDeleteCommand(SideBarCommand):
    def run(self, paths):
        if len(paths) == 1:
            message = "Delete %s?" % paths[0]
        else:
            message = "Delete %d items?" % len(paths)

        if sublime.ok_cancel_dialog(message, "Delete"):
            import Default.send2trash as send2trash
            try:
                for path in paths:
                    send2trash.send2trash(path)
            except:
                self.window.status_message("Unable to delete")

    def description(self):
        return 'Delete'


class SideBarMenuRunOrOpenCommand(SideBarCommand):
    def run(self, paths):
        os.startfile(self.get_path(paths))
