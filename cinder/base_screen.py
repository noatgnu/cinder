from textual.binding import Binding
from textual.screen import Screen


class BaseScreen(Screen):
    AUTO_FOCUS = False
    BINDINGS = [
        Binding(key="ctrl+q", action="quit", description="Exit the application"),
    ]

    def on_mount(self) -> None:
        self.styles.background = "darkred"
        self.styles.border = ("heavy", "white")