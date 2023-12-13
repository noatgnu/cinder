from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Grid, Horizontal, Container

from cinder.base_screen import BaseScreen
from textual.widgets import Header, Label, Button, Footer, Placeholder, Input, Markdown, Static

description_markdown = """
# Cinder Settings

Here you can configure the settings for Cinder including remote connection to Corpus Remote Server
"""

class SettingsScreen(BaseScreen):
    AUTO_FOCUS = False
    BINDINGS = [
        Binding(key="ctrl+q", action="quit", description="Exit the application"),
        Binding(key="ctrl+s", action="save", description="Save settings"),
    ]
    CSS_PATH = "settings.tcss"

    def compose(self) -> ComposeResult:
        yield Header(True, name="Cinder")
        yield Markdown(description_markdown, classes="description")
        yield Container(
            Label("Corpus Host: "),
            Input(id="central_rest_api_host", classes="small-input", value=self.app.config["central_rest_api"]["host"]),
            Label("Corpus Port: "),
            Input(id="central_rest_api_port", classes="small-input",
                  value=str(self.app.config["central_rest_api"]["port"])),
            Label("Corpus Protocol: "),
            Input(id="central_rest_api_protocol", classes="small-input",
                  value=self.app.config["central_rest_api"]["protocol"]),
            Label("Corpus API Key: "),
            Input(id="central_rest_api_key", classes="small-input",
                  value=self.app.config["central_rest_api"]["api_key"]),
            id="central_rest_api",
        )
        yield Footer()

    def on_mount(self) -> None:
        central_rest_api = self.query_one("#central_rest_api", Container)
        central_rest_api.styles.align = ("left", "top")
        central_rest_api.styles.padding = 2

    async def action_save(self):
        pass