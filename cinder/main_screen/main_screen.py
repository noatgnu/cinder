import json
import os.path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header, Label, Button, Footer

from cinder.base_screen import BaseScreen
from appdirs import AppDirs
import sqlite3

from cinder.project import ProjectDatabase


class MainScreen(BaseScreen):
    AUTO_FOCUS = False
    BINDINGS = [
        Binding(key="ctrl+q", action="go_quit", description="Exit the application"),
        Binding(key="ctrl+s", action="go_to_settings", description="Go to settings screen"),
    ]
    CSS_PATH = "main_screen.tcss"


    def compose(self) -> ComposeResult:
        yield Header(True, name="Cinder")

        yield Horizontal(Label(r"""
  ____ ___ _   _ ____  _____ ____  
 / ___|_ _| \ | |  _ \| ____|  _ \ 
| |    | ||  \| | | | |  _| | |_) |
| |___ | || |\  | |_| | |___|  _ < 
 \____|___|_| \_|____/|_____|_| \_\
""", id="cinder-title"),classes="box")
        yield Horizontal(
            Button("Upload Searched Raw File", variant="error", id="go-to-upload-raw", disabled=True, classes="m-1"),
            Button("Upload Differential Analysis", variant="error", id="go-to-upload-diff", disabled=True, classes="m-1"),
            Button("Upload MS Raw Files", variant="error", id="go-to-upload-ms", disabled=True, classes="m-1"),
            Button("Data Manager", variant="error", id="go-to-data-manager", classes="m-1"),
            classes="box")
        yield Footer()

    def on_mount(self) -> None:

        self.notify("Welcome to Cinder")
        self.app.config_dir = AppDirs("Cinder", "Cinder")
        os.makedirs(self.app.config_dir.user_config_dir, exist_ok=True)
        self.app.config = {"central_rest_api": {
            "host": "localhost",
            "port": 80,
            "protocol": "http",
            "api_key": ""
        }}
        if os.path.exists("data_manager_config.json"):
            with open(os.path.join(self.app.config_dir.user_config_dir, "data_manager_config.json"), "r") as f:
                config = json.load(f)
                for key in config:
                    self.app.config[key] = config[key]
        else:
            with open(os.path.join(self.app.config_dir.user_config_dir, "data_manager_config.json"), "w") as f:
                json.dump(self.app.config, f)

        self.app.db = ProjectDatabase(os.path.join(self.app.config_dir.user_config_dir, "data_manager.db"))

    @on(Button.Pressed, "#go-to-upload-raw")
    async def go_to_upload_raw(self, event):
        self.notify("Entering Searched Raw File Upload Screen")
        await self.app.push_screen("upload_screen")

    @on(Button.Pressed, "#go-to-data-manager")
    async def go_to_data_manager(self, event):
        self.notify("Entering Data Manager Screen")
        await self.app.push_screen("project_manager_screen")

    async def action_go_to_settings(self):
        self.notify("Entering Settings Screen")
        await self.app.push_screen("settings_screen")


