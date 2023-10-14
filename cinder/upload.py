from textual import on
from textual.app import App, ComposeResult

import logging

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header, Button, Static, Label

from cinder.upload_raw_file import UploadScreen, FolderWalk

class MainScreen(Screen):
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
            Button("Upload Searched Raw File", variant="error", id="go-to-upload-raw", classes="m-1"),
            Button("Upload Differential Analysis", variant="error", id="go-to-upload-diff", classes="m-1"),
            Button("Upload MS Raw Files", variant="error", id="go-to-upload-ms", disabled=True, classes="m-1"),
            classes="box")

    def on_mount(self) -> None:
        self.styles.background = "darkred"
        self.styles.border = ("heavy", "white")
        self.styles.align = ("center", "middle")

    @on(Button.Pressed, "#go-to-upload-raw")
    async def go_to_upload_raw(self, event):
        self.notify("Entering Searched Raw File Upload Screen")
        await self.app.push_screen("upload_screen")

class Cinder(App):
    CSS_PATH = "upload.tcss"
    SCREENS = {"upload_screen": UploadScreen(), "directory_walk_upload": FolderWalk(), "main_screen": MainScreen()}

    def on_mount(self) -> None:
        self.push_screen("main_screen")

def main():
    app = Cinder()
    app.run()

if __name__ == "__main__":
    logging.basicConfig(filename="cinder.log", level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    logging.log(logging.DEBUG, "Starting Cinder")
    app = Cinder()
    app.run()