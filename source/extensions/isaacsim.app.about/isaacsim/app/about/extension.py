# SPDX-FileCopyrightText: Copyright (c) 2018-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path

import carb
import carb.settings
import omni.client
import omni.ext
import omni.kit.app
import omni.kit.ui
from isaacsim.core.version import get_version
from omni import ui
from omni.kit.menu.utils import MenuItemDescription, add_menu_items, build_submenu_dict

WINDOW_NAME = "About"
DISCONNECTED = "** disconnected **"
QUERYING = "** querying **"

_extension_instance = None


class AboutExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        menu_dict = build_submenu_dict(
            [
                MenuItemDescription(name="Help/About", onclick_fn=lambda *_: self._on_menu_show_about()),
            ],
        )
        for group in menu_dict:
            add_menu_items(menu_dict[group], group)

        self.get_values()

        global _extension_instance
        _extension_instance = self

    def on_shutdown(self):
        global _extension_instance
        _extension_instance = None

        self._about_menu = None

    def get_values(self):
        settings = carb.settings.get_settings()
        self.kit_version = omni.kit.app.get_app().get_build_version()
        # Minimize Kit SDK version for release
        if self.kit_version:
            kit_version, _ = self.kit_version.split("+")
            self.kit_version = kit_version
        self.nucleus_version = DISCONNECTED
        self.client_library_version = omni.client.get_version()
        # Minimize Client Library version for release
        if self.client_library_version:
            client_lib_version, _ = self.client_library_version.split("+")
            client_lib_version, _ = client_lib_version.split("-")
            self.client_library_version = client_lib_version
        # Get App Name and Version
        self.app_name = settings.get("/app/window/title")
        self.app_version_core, self.app_version_prerel, _, _, _, _, _, _ = get_version()
        self.app_version = f"{self.app_version_core}-{self.app_version_prerel}"

    @staticmethod
    def _resize_window(window: ui.Window, scrolling_frame: ui.ScrollingFrame):
        scrolling_frame.width = ui.Pixel(window.width - 10)
        scrolling_frame.height = ui.Pixel(window.height - 235)

    def _on_menu_show_about(self):
        plugins = carb.get_framework().get_plugins()
        plugins = sorted(plugins, key=lambda x: x.impl.name)
        self.menu_show_about(plugins)

    def menu_show_about(self, plugins):
        info = f"App Name: {self.app_name}\nApp Version: {self.app_version}\nKit SDK Version{self.kit_version}\nClient Library Version: {self.client_library_version}"

        def hide(w):
            w.visible = False

        def copy_to_clipboard(x, y, button, modifier):
            if button != 1:
                return

            try:
                import pyperclip
            except ImportError:
                carb.log_warn("Could not import pyperclip.")
                return
            try:
                pyperclip.copy(info)
            except pyperclip.PyperclipException:
                carb.log_warn(pyperclip.EXCEPT_MSG)
                return

        window = ui.Window(
            "About", width=800, height=510, flags=ui.WINDOW_FLAGS_NO_SCROLLBAR | ui.WINDOW_FLAGS_NO_DOCKING
        )

        with window.frame:
            with ui.ZStack():
                with ui.VStack(style={"margin": 5}, width=0, height=0):
                    ui.Label(f"App Name: {self.app_name}", style={"font_size": 18})
                    ui.Label(f"App Version: {self.app_version}", style={"font_size": 18})
                    ui.Label(f"Kit SDK Version: {self.kit_version}", style={"font_size": 18})
                    ui.Label(f"Client Library Version: {self.client_library_version}", style={"font_size": 18})
                    # ui.Label(f"Nucleus Server Version: {self.nucleus_version}", style={"font_size": 18})    # TODO JS
                    ui.Spacer(height=16)
                    ui.Label("Loaded plugins", style={"font_size": 16})
                    ui.Separator()
                    scrolling_frame = ui.ScrollingFrame(
                        width=790,
                        height=240,
                        horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                        vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON,
                        style={"margin_width": 2, "margin_height": 3},
                    )
                    with scrolling_frame:
                        with ui.VStack(height=0):
                            for p in plugins:
                                ui.Label(f"{p.impl.name} {p.interfaces}", tooltip=p.libPath)

                    ui.Separator()
                    ui.Button("OK", width=64, clicked_fn=lambda w=window: hide(w))
                ui.Button(" ", height=128, style={"background_color": 0x00000000}, mouse_pressed_fn=copy_to_clipboard)

        AboutExtension._resize_window(window, scrolling_frame)
        window.set_width_changed_fn(lambda value, w=window, f=scrolling_frame: AboutExtension._resize_window(w, f))
        window.set_height_changed_fn(lambda value, w=window, f=scrolling_frame: AboutExtension._resize_window(w, f))

        return window


def get_instance():
    return _extension_instance
