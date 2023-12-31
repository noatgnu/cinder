from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import Screen, ModalScreen
from textual.widgets import Label, Button


class ModalQuitScreen(ModalScreen):
    CSS_PATH = "modal_quit_screen.tcss"

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to quit", id="question"),
            Button("Quit", id="quit", variant="error"),
            Button("Cancel", id="cancel", variant="primary"),
            id="modal-quit"
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "quit":
            self.app.exit()
        else:
            self.app.pop_screen()
