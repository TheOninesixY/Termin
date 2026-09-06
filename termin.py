#!/usr/bin/env python3
import os
import pwd
import sys
import shutil
import warnings
from urllib.parse import unquote, urlparse
import gi

warnings.filterwarnings("ignore", category=DeprecationWarning)

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import Gtk, Adw, Vte, GLib, Gio, Pango, Gdk

TRANSLATIONS = {
    "en": {
        "copy": "Copy",
        "paste": "Paste",
        "select_all": "Select All",
        "copy_terminal": "Copy Terminal",
        "copy_markdown": "Copy as Markdown",
    },
    "zh_CN": {
        "copy": "复制",
        "paste": "粘贴",
        "select_all": "全选",
        "copy_terminal": "复制终端",
        "copy_markdown": "复制为 Markdown",
    },
    "zh_TW": {
        "copy": "複製",
        "paste": "貼上",
        "select_all": "全選",
        "copy_terminal": "複製終端",
        "copy_markdown": "複製為 Markdown",
    },
    "zh_HK": {
        "copy": "複製",
        "paste": "貼上",
        "select_all": "全選",
        "copy_terminal": "複製終端",
        "copy_markdown": "複製為 Markdown",
    },
    "ja": {
        "copy": "コピー",
        "paste": "貼り付け",
        "select_all": "すべて選択",
        "copy_terminal": "ターミナルをコピー",
        "copy_markdown": "Markdown としてコピー",
    },
    "ko": {
        "copy": "복사",
        "paste": "붙여넣기",
        "select_all": "전체 선택",
        "copy_terminal": "터미널 복사",
        "copy_markdown": "Markdown으로 복사",
    },
}


def get_translations():
    lang_list = GLib.get_language_names()
    for lang in lang_list:
        clean_lang = lang.split(".")[0].split("@")[0]
        if clean_lang in TRANSLATIONS:
            return TRANSLATIONS[clean_lang]
        short_lang = clean_lang.split("_")[0]
        if short_lang in TRANSLATIONS:
            return TRANSLATIONS[short_lang]
        if short_lang == "zh":
            lower = clean_lang.lower()
            if "tw" in lower or "hant" in lower or "hk" in lower:
                return TRANSLATIONS["zh_TW"]
            return TRANSLATIONS["zh_CN"]
    return TRANSLATIONS["en"]


def parse_rgba(hex_color):
    rgba = Gdk.RGBA()
    rgba.parse(hex_color)
    return rgba


def apply_theme_styles():
    css = """
    window,
    window.background,
    headerbar,
    toolbarview {
        background-color: #282c34;
    }
    headerbar {
        background-color: #282c34;
        border: none;
        box-shadow: none;
    }
    .termin-toolbar,
    .termin-headerbar {
        padding: 0;
        margin: 0;
    }
    """
    provider = Gtk.CssProvider()
    if hasattr(provider, "load_from_string"):
        provider.load_from_string(css)
    else:
        provider.load_from_data(css.encode("utf-8"))

    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


class TerminWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.current_path = "~"
        self.shell_name = "Shell"
        self.target_scroll_val = None
        self.scroll_tick_id = None
        self.settings = None
        self.portal_proxy = None
        self.is_flatpak = os.path.exists("/.flatpak-info")

        self.set_default_size(800, 500)
        self.set_title(self.shell_name)

        self.toolbar_view = Adw.ToolbarView()
        self.toolbar_view.add_css_class("termin-toolbar")

        self.header_bar = Adw.HeaderBar()
        self.header_bar.add_css_class("termin-headerbar")
        self.toolbar_view.add_top_bar(self.header_bar)

        self.terminal = Vte.Terminal()
        self.terminal.add_css_class("termin-terminal")
        self.terminal.set_vexpand(True)
        self.terminal.set_hexpand(True)
        self.terminal.set_scroll_on_output(False)
        self.terminal.set_scroll_on_keystroke(True)
        self.terminal.set_mouse_autohide(True)
        self.terminal.set_cursor_shape(Vte.CursorShape.IBEAM)

        if hasattr(self.terminal, "set_scroll_unit_is_pixels"):
            self.terminal.set_scroll_unit_is_pixels(True)
        if hasattr(self.terminal, "set_enable_fallback_scrolling"):
            self.terminal.set_enable_fallback_scrolling(True)

        self.setup_colors()

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.set_kinetic_scrolling(True)
        self.scrolled_window.set_overlay_scrolling(True)
        self.scrolled_window.set_child(self.terminal)

        self.setup_fonts()
        self.setup_smooth_scrolling()
        self.setup_context_menu()
        self.terminal.connect("window-title-changed", self.on_window_title_changed)
        self.terminal.connect("current-directory-uri-changed", self.on_directory_changed)
        self.terminal.connect("child-exited", self.on_child_exited)
        self.terminal.connect("realize", self.on_terminal_realize)

        self.setup_key_controllers()
        self.connect("notify::fullscreened", self.on_fullscreen_changed)

        self.toolbar_view.set_content(self.scrolled_window)
        self.set_content(self.toolbar_view)

        self.spawn_session()

    def on_terminal_realize(self, widget):
        self.update_terminal_margins()

    def update_terminal_margins(self):
        char_width = self.terminal.get_char_width()
        if char_width > 0:
            self.terminal.set_margin_start(char_width)
            self.terminal.set_margin_end(char_width)

    def on_window_title_changed(self, terminal):
        title = terminal.get_window_title() if hasattr(terminal, "get_window_title") else None
        if title:
            self.set_title(title)
        else:
            self.set_title(self.shell_name)

    def setup_colors(self):
        bg = parse_rgba("#282c34")
        fg = parse_rgba("#abb2bf")
        cursor = parse_rgba("#ffffff")

        palette_hex = [
            "#282c34",
            "#e06c75",
            "#98c379",
            "#e5c07b",
            "#61afef",
            "#c678dd",
            "#56b6c2",
            "#abb2bf",
            "#5c6370",
            "#be5046",
            "#98c379",
            "#e5c07b",
            "#61afef",
            "#c678dd",
            "#56b6c2",
            "#ffffff",
        ]
        palette = [parse_rgba(c) for c in palette_hex]

        self.terminal.set_colors(fg, bg, palette)
        if hasattr(self.terminal, "set_color_cursor"):
            self.terminal.set_color_cursor(cursor)
        if hasattr(self.terminal, "set_color_cursor_foreground"):
            self.terminal.set_color_cursor_foreground(bg)

    def setup_smooth_scrolling(self):
        controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES
            | Gtk.EventControllerScrollFlags.KINETIC
        )
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("scroll", self.on_scroll)
        self.scrolled_window.add_controller(controller)

    def on_scroll(self, controller, dx, dy):
        event = controller.get_current_event()
        if event and hasattr(event, "get_device"):
            device = event.get_device()
            if device and hasattr(device, "get_source"):
                source = device.get_source()
                touchpad_sources = (
                    getattr(Gdk.InputSource, "TOUCHPAD", None),
                    getattr(Gdk.InputSource, "TOUCHSCREEN", None),
                )
                if source in touchpad_sources:
                    return False

        adj = self.scrolled_window.get_vadjustment()
        if not adj:
            return False

        step = adj.get_step_increment()
        if step <= 0:
            step = 30.0

        if self.target_scroll_val is None:
            self.target_scroll_val = adj.get_value()

        lower = adj.get_lower()
        upper = adj.get_upper() - adj.get_page_size()
        if upper < lower:
            upper = lower

        scroll_distance = dy * (step * 2.5 if abs(dy) <= 1.0 else dy * 4.0)
        self.target_scroll_val = max(lower, min(upper, self.target_scroll_val + scroll_distance))

        if self.scroll_tick_id is None:
            self.scroll_tick_id = self.scrolled_window.add_tick_callback(self.on_scroll_tick)

        return True

    def on_scroll_tick(self, widget, frame_clock):
        adj = self.scrolled_window.get_vadjustment()
        if not adj or self.target_scroll_val is None:
            self.scroll_tick_id = None
            return GLib.SOURCE_REMOVE

        curr = adj.get_value()
        diff = self.target_scroll_val - curr

        if abs(diff) < 0.5:
            adj.set_value(self.target_scroll_val)
            self.target_scroll_val = None
            self.scroll_tick_id = None
            return GLib.SOURCE_REMOVE

        adj.set_value(curr + diff * 0.22)
        return GLib.SOURCE_CONTINUE

    def setup_key_controllers(self):
        controller = Gtk.EventControllerKey.new()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)

    def setup_context_menu(self):
        # 注册动作
        copy_action = Gio.SimpleAction.new("copy", None)
        copy_action.connect("activate", self.on_action_copy)
        self.add_action(copy_action)

        paste_action = Gio.SimpleAction.new("paste", None)
        paste_action.connect("activate", self.on_action_paste)
        self.add_action(paste_action)

        select_all_action = Gio.SimpleAction.new("select_all", None)
        select_all_action.connect("activate", self.on_action_select_all)
        self.add_action(select_all_action)

        copy_terminal_action = Gio.SimpleAction.new("copy_terminal", None)
        copy_terminal_action.connect("activate", self.on_action_copy_terminal)
        self.add_action(copy_terminal_action)

        copy_markdown_action = Gio.SimpleAction.new("copy_markdown", None)
        copy_markdown_action.connect("activate", self.on_action_copy_markdown)
        self.add_action(copy_markdown_action)

        # 构建菜单模型
        t = get_translations()
        menu = Gio.Menu()
        menu.append(t["copy"], "win.copy")
        menu.append(t["paste"], "win.paste")
        menu.append(t["select_all"], "win.select_all")

        terminal_section = Gio.Menu()
        terminal_section.append(t["copy_terminal"], "win.copy_terminal")
        terminal_section.append(t["copy_markdown"], "win.copy_markdown")
        menu.append_section(None, terminal_section)

        self.context_popover = Gtk.PopoverMenu.new_from_model(menu)
        self.context_popover.add_css_class("menu")
        self.context_popover.set_parent(self.terminal)
        self.context_popover.set_has_arrow(False)

        # 右键手势
        gesture = Gtk.GestureClick.new()
        gesture.set_button(Gdk.BUTTON_SECONDARY)
        gesture.connect("pressed", self.on_context_menu_pressed)
        self.terminal.add_controller(gesture)

    def get_terminal_full_text(self):
        try:
            if hasattr(self.terminal, "get_text_format"):
                text = self.terminal.get_text_format(Vte.Format.TEXT)
                if text is not None:
                    return text
        except Exception:
            pass
        return None

    def on_action_copy_terminal(self, action, param):
        text = self.get_terminal_full_text()
        if text is not None:
            clipboard = self.get_display().get_clipboard()
            clipboard.set(text.rstrip("\n"))
        else:
            had_selection = self.terminal.get_has_selection()
            self.terminal.select_all()
            self.terminal.copy_clipboard_format(Vte.Format.TEXT)
            if not had_selection:
                self.terminal.unselect_all()

    def on_action_copy_markdown(self, action, param):
        text = self.get_terminal_full_text()
        if text is not None:
            shell_tag = self.shell_name.lower() if self.shell_name else "sh"
            content = text.rstrip("\n")
            md = f"```{shell_tag}\n{content}\n```"
            clipboard = self.get_display().get_clipboard()
            clipboard.set(md)

    def on_context_menu_pressed(self, gesture, n_press, x, y):
        # 更新复制按钮状态（是否有选中文本）
        copy_action = self.lookup_action("copy")
        if copy_action:
            copy_action.set_enabled(self.terminal.get_has_selection())

        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self.context_popover.set_pointing_to(rect)
        self.context_popover.popup()

    def on_action_copy(self, action, param):
        self.terminal.copy_clipboard_format(Vte.Format.TEXT)

    def on_action_paste(self, action, param):
        self.terminal.paste_clipboard()

    def on_action_select_all(self, action, param):
        self.terminal.select_all()

    def on_fullscreen_changed(self, window, pspec):
        is_fullscreen = self.is_fullscreen()
        self.header_bar.set_visible(not is_fullscreen)

    def toggle_fullscreen(self):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    def is_foreground_process_running(self):
        try:
            pty = self.terminal.get_pty()
            if pty:
                fd = pty.get_fd()
                tc_pgrp = os.tcgetpgrp(fd)
                shell_pgrp = os.getpgid(0)
                # 如果前台进程组不等于终端所在进程组，且有效
                if tc_pgrp > 0:
                    return tc_pgrp != shell_pgrp
        except Exception:
            pass
        return False

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_F11:
            self.toggle_fullscreen()
            return True

        has_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        has_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        has_alt = bool(state & Gdk.ModifierType.ALT_MASK)

        if has_ctrl and not has_alt:
            # Ctrl+Shift 组合键始终有效
            if has_shift:
                if keyval in (Gdk.KEY_c, Gdk.KEY_C):
                    self.terminal.copy_clipboard_format(Vte.Format.TEXT)
                    return True
                if keyval in (Gdk.KEY_v, Gdk.KEY_V):
                    self.terminal.paste_clipboard()
                    return True
                if keyval in (Gdk.KEY_a, Gdk.KEY_A):
                    self.terminal.select_all()
                    return True

            # 纯 Ctrl 快捷键智能行为
            if not has_shift:
                # 当有选中文本时，Ctrl+C 进行复制，否则保留原本的 SIGINT 中断信号
                if keyval in (Gdk.KEY_c, Gdk.KEY_C):
                    if self.terminal.get_has_selection():
                        self.terminal.copy_clipboard_format(Vte.Format.TEXT)
                        return True

                # Ctrl+A 全选
                if keyval in (Gdk.KEY_a, Gdk.KEY_A):
                    if self.terminal.get_has_selection():
                        self.terminal.select_all()
                        return True

                # 当前若没有运行前台命令（在等待输入提示符），Ctrl+V 直接粘贴
                if keyval in (Gdk.KEY_v, Gdk.KEY_V):
                    if not self.is_foreground_process_running():
                        self.terminal.paste_clipboard()
                        return True

        return False

    def on_directory_changed(self, terminal):
        uri = terminal.get_current_directory_uri()
        if not uri:
            return

        parsed = urlparse(uri)
        path = unquote(parsed.path)
        home = GLib.get_home_dir()

        if path == home:
            self.current_path = "~"
        elif path.startswith(home + "/"):
            self.current_path = "~" + path[len(home):]
        else:
            self.current_path = path

    def setup_fonts(self):
        if self.is_flatpak:
            try:
                self.portal_proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SESSION,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.freedesktop.portal.Desktop",
                    "/org/freedesktop/portal/desktop",
                    "org.freedesktop.portal.Settings",
                    None,
                )
                self.portal_proxy.connect("g-signal", self.on_portal_setting_changed)
            except Exception:
                self.portal_proxy = None
        else:
            schema_id = "org.gnome.desktop.interface"
            source = Gio.SettingsSchemaSource.get_default()
            if source and source.lookup(schema_id, True):
                try:
                    self.settings = Gio.Settings.new(schema_id)
                    self.settings.connect("changed::monospace-font-name", self.on_font_changed)
                except Exception:
                    self.settings = None

        self.apply_font()

    def on_portal_setting_changed(self, proxy, sender_name, signal_name, parameters):
        if signal_name == "SettingChanged":
            try:
                namespace, key, value = parameters.unpack()
                if namespace == "org.gnome.desktop.interface" and key == "monospace-font-name":
                    val = value
                    while isinstance(val, GLib.Variant):
                        val = val.unpack()
                    if isinstance(val, str) and val.strip():
                        self.set_terminal_font(val.strip())
            except Exception:
                pass

    def on_font_changed(self, settings, key):
        self.apply_font()

    def read_portal_font(self):
        if not self.portal_proxy:
            return None
        try:
            res = self.portal_proxy.call_sync(
                "Read",
                GLib.Variant("(ss)", ("org.gnome.desktop.interface", "monospace-font-name")),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            if res:
                outer = res.unpack()
                if outer and len(outer) > 0:
                    val = outer[0]
                    while isinstance(val, GLib.Variant):
                        val = val.unpack()
                    if isinstance(val, str) and val.strip():
                        return val.strip()
        except Exception:
            pass
        return None

    def read_host_gsettings_font(self):
        if not self.is_flatpak:
            return None
        try:
            res = GLib.spawn_command_line_sync(
                "flatpak-spawn --host gsettings get org.gnome.desktop.interface monospace-font-name"
            )
            if res and res[0] and res[1]:
                val = res[1].decode("utf-8", errors="ignore").strip().strip("'").strip('"')
                if val:
                    return val
        except Exception:
            pass
        return None

    def get_system_monospace_font(self):
        if self.is_flatpak:
            portal_font = self.read_portal_font()
            if portal_font:
                return portal_font

            host_font = self.read_host_gsettings_font()
            if host_font:
                return host_font

        if self.settings:
            try:
                font = self.settings.get_string("monospace-font-name")
                if font:
                    return font
            except Exception:
                pass

        return "Monospace 11"

    def apply_font(self):
        font_name = self.get_system_monospace_font()
        self.set_terminal_font(font_name)

    def set_terminal_font(self, font_name):
        if not font_name:
            font_name = "Monospace 11"
        desc = Pango.FontDescription.from_string(font_name)
        self.terminal.set_font(desc)
        self.update_terminal_margins()

    def detect_shell(self):
        if self.is_flatpak:
            try:
                user = GLib.get_user_name()
                res = GLib.spawn_command_line_sync(f"flatpak-spawn --host getent passwd {user}")
                if res and res[0] and res[1]:
                    entry = res[1].decode("utf-8", errors="ignore").strip().split(":")
                    if len(entry) >= 7 and entry[6] and os.path.isabs(entry[6]):
                        return entry[6]
            except Exception:
                pass

            try:
                res = GLib.spawn_command_line_sync("flatpak-spawn --host printenv SHELL")
                if res and res[0] and res[1]:
                    shell = res[1].decode("utf-8", errors="ignore").strip()
                    if shell and os.path.isabs(shell):
                        return shell
            except Exception:
                pass

        try:
            return pwd.getpwuid(os.getuid()).pw_shell
        except Exception:
            return os.environ.get("SHELL", "/bin/bash")

    def spawn_session(self):
        shell_path = self.detect_shell()
        raw_name = os.path.basename(shell_path)
        self.shell_name = raw_name.capitalize() if raw_name else "Shell"
        self.set_title(self.shell_name)

        working_dir = GLib.get_home_dir()

        if self.is_flatpak:
            pty_flags = Vte.PtyFlags.DEFAULT
            host_spawn_bin = "/app/bin/host-spawn" if os.path.exists("/app/bin/host-spawn") else "host-spawn"
            argv = [
                host_spawn_bin,
                shell_path,
            ]
            envv = GLib.get_environ()
        else:
            pty_flags = Vte.PtyFlags.DEFAULT
            argv = [shell_path]
            envv = GLib.environ_setenv(GLib.get_environ(), "TERM_PROGRAM", "Termin", True)
            envv = GLib.environ_setenv(envv, "COLORTERM", "truecolor", True)
            envv = GLib.environ_setenv(envv, "TERM", "xterm-256color", True)

        self.terminal.spawn_async(
            pty_flags=pty_flags,
            working_directory=working_dir,
            argv=argv,
            envv=envv,
            spawn_flags=GLib.SpawnFlags.SEARCH_PATH,
            timeout=-1,
        )

    def on_child_exited(self, terminal, status):
        self.close()


class TerminApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.theoninesixy.Termin",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

    def do_activate(self):
        manager = Adw.StyleManager.get_default()
        manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        apply_theme_styles()

        self.set_accels_for_action("win.copy", ["<Shift><Control>C", "<Control><Shift>C"])
        self.set_accels_for_action("win.paste", ["<Shift><Control>V", "<Control><Shift>V"])
        self.set_accels_for_action("win.select_all", ["<Shift><Control>A", "<Control><Shift>A"])

        win = TerminWindow(application=self)
        self.add_window(win)
        win.present()


def main():
    app = TerminApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())