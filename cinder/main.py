from textual.app import App

import logging

from cinder.cinderproject.project import ProjectManagerScreen, ProjectScreen
from cinder.cindersettings.settings import SettingsScreen
from cinder.main_screen.main_screen import MainScreen
from cinder.upload_raw_file import UploadScreen, FolderWalk
from cinder.util_screen.modal_quit import ModalUpdateTextScreen


class Cinder(App):
    CSS_PATH = "upload.tcss"
    SCREENS = {
        "upload_screen": UploadScreen(),
        "directory_walk_upload": FolderWalk(),
        "main_screen": MainScreen(),
        "project_manager_screen": ProjectManagerScreen(),
        "project_screen": ProjectScreen(),
        "settings_screen": SettingsScreen(),
        "modal_quit": ModalUpdateTextScreen(),
    }

    def on_mount(self) -> None:
        print(self.SCREENS)
        self.push_screen("main_screen")


def main():
    app = Cinder()
    app.run()

if __name__ == "__main__":
    logging.basicConfig(filename="cinder.log", level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    logging.log(logging.DEBUG, "Starting Cinder")
    app = Cinder()
    app.run()