from textual.binding import Binding
from textual.screen import Screen


class BaseScreen(Screen):
    AUTO_FOCUS = False
    BINDINGS = [
        Binding(key="ctrl+q", action="go_quit", description="Exit the application"),
    ]

    def on_mount(self) -> None:
        self.styles.background = "darkred"
        self.styles.border = ("heavy", "white")

    async def action_go_quit(self):
        await self.app.push_screen("modal_quit")