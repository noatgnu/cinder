
from textual.app import App

import logging

from cinder.upload_raw_file import UploadScreen


class Cinder(App):
    CSS_PATH = "upload.tcss"
    SCREENS = {"upload_screen": UploadScreen()}
    def on_mount(self) -> None:
        self.push_screen("upload_screen")

def main():
    app = Cinder()
    app.run()

if __name__ == "__main__":
    logging.basicConfig(filename="cinder.log", level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    logging.log(logging.DEBUG, "Starting Cinder")
    app = Cinder()
    app.run()