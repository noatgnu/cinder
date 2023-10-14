import json
import tempfile
from typing import Type

import httpx
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen, ModalScreen, ScreenResultType
from textual.widgets import Footer, Header, Input, Markdown, Button, Static, SelectionList, Label, OptionList, Select, \
    LoadingIndicator
from textual.containers import Vertical, Horizontal, VerticalScroll, Container, Grid
import logging
import pandas as pd

from cinder.cindergpt.gpt import gpt_get_index
from cinder.condition_assignment import ConditionAssignment
import os


host = os.environ.get("CLAVICLE_HOST", "localhost")
port = os.environ.get("CLAVICLE_PORT", "8000")
protocol = os.environ.get("CLAVICLE_PROTOCOL", "http")


class FolderWalk(ModalScreen[str]):
    def compose(self) -> ComposeResult:
        yield Grid(
            Input(placeholder="Folder path", id="folder-path-input"),
            Button("Cancel", id="cancel-modal-button", variant="error"),
            Button("Load", id="load-modal-button", variant="primary"),
            id="folder-input-section"
        )

    @on(Button.Pressed, "#cancel-modal-button")
    async def cancel(self, event: Button.Pressed):
        self.dismiss("")

    @on(Button.Pressed, "#load-modal-button")
    async def load(self, event: Button.Pressed):
        self.dismiss(self.query_one("#folder-path-input", Input).value)


class FolderWalkOneByOne(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Grid(
            Label(id="folder-path-input"),
            Button("Cancel", id="cancel-modal-button", variant="error"),
            Button("Load", id="load-modal-button", variant="primary"),
            id="folder-input-section"
        )

class UploadScreen(Screen):
    BINDINGS = [
        Binding(key="ctrl+q", action="quit", description="Exit the application"),
        Binding(key="ctrl+s", action="submit_data", description="Submit data to server"),
        Binding(key="ctrl+l", action="directory_walk", description="Walk directory for input files"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(True, name="Cinder")

        yield Horizontal(
            Vertical(Input(placeholder="Filepath", id="input-file"), classes="column"),
            Button("Load", variant="primary", id="load-button"), id="file-input-section"
        )
        yield LoadingIndicator(id="loading-indicator", classes="loading-indicator-inactive")
        yield Vertical(
            Horizontal(
                Vertical(
                    Vertical(
                        Container(
                            Label("Select sample columns"), id="selection-list-label"
                        ),
                        Input(placeholder="Select column by index", id="input-column-index"),
                        id="column-by-index"),
                    VerticalScroll(
                        SelectionList[str](
                            id="selection-list",
                        ),
                        id="selection-list-container"
                    ),
                    Container(Button("Auto select with ChatGPT", id="auto-select-button", variant="primary"), id="auto-select-button-container"
                    ),
                    Container(Label("Select index column"), id="index-column-selection-label"),
                    Vertical(

                        id="select-index-column-container"
                    ),
                    Container(Markdown("", id="index-summary"), id="index-summary-container"),

                    id="column-selection",
                ),
                ConditionAssignment(id="condition-assignment"),
            ), id="main-uploading-view", classes="main-uploading-view-inactive"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.screen.styles.background = "darkred"
        self.screen.styles.border = ("heavy", "white")
        condition_assignment = self.query_one("#condition-assignment", VerticalScroll)
        condition_assignment.border_title = "Assign Conditions"

        self.loading_indicator = self.query_one("#loading-indicator", LoadingIndicator)

    @on(Button.Pressed, "#load-button")
    async def load_file(self, event: Button.Pressed) -> None:
        self.loading_indicator.remove_class("loading-indicator-inactive")
        self.loading_indicator.add_class("loading-indicator-active")

        self.file_path = self.query_one("#input-file", Input).value.replace('"', "").replace("\\", "/")
        if self.file_path.endswith(".csv"):
            self.df = pd.read_csv(self.file_path)
        elif self.file_path.endswith(".tsv"):
            self.df = pd.read_csv(self.file_path, sep="\t")
        elif self.file_path.endswith(".txt"):
            self.df = pd.read_csv(self.file_path, sep="\t")
        else:
            self.notify("File type not supported.", severity="error")

        if getattr(self, "df", None) is not None:
            self.columns = self.df.columns.tolist()
            selection_list_container = self.query_one("#selection-list-container", VerticalScroll)
            await selection_list_container.remove_children()
            await selection_list_container.mount(SelectionList[str](id="selection-list"))
            selection = self.query_one("#selection-list", SelectionList)
            index_column_container = self.query_one("#select-index-column-container", Vertical)
            await index_column_container.remove_children()
            await index_column_container.mount(Select(id="index-column-selection", options=[(i, i) for i in self.columns]))
            selection.add_options([(f"{n} {i}", i) for n, i in enumerate(self.columns)])
            condition_assignment = self.query_one("#condition-assignment", ConditionAssignment)
            condition_assignment.sample_dict = {}
            condition_assignment.selected_sample = ""
            await condition_assignment.update_view()
            self.query_one("#group-name-input", Input).value = ""
            self.query_one("#main-uploading-view", Vertical).remove_class("main-uploading-view-inactive")
            self.query_one("#main-uploading-view", Vertical).add_class("main-uploading-view-active")
        self.query_one("#loading-indicator", LoadingIndicator).remove_class("loading-indicator-active")
        self.query_one("#loading-indicator", LoadingIndicator).add_class("loading-indicator-inactive")

    @on(Input.Submitted, "#input-file")
    async def on_file_input_submit(self, event: Input.Submitted) -> None:
        await self.load_file(Button.Pressed(button=self.query_one("#load-button", Button)))

    @on(Input.Submitted, "#group-name-input")
    async def on_group_name_submit(self, event: Input.Submitted) -> None:
        container = self.query_one("#condition-assignment", ConditionAssignment)
        data = self.query_one("#group-name-input", Input).value
        if container.selected_sample != "":
            container.sample_dict[container.selected_sample]["group"] = data
            container.sample_dict[container.selected_sample][
                "option-text"] = f"{container.selected_sample} ({data})"
            await container.update_view()

    @on(SelectionList.SelectedChanged, "#selection-list")
    async def update_selected_columns(self) -> None:
        container = self.query_one("#condition-assignment", ConditionAssignment)
        selected = self.query_one("#selection-list", SelectionList).selected
        to_remove = []
        for i in container.sample_dict.keys():
            if i not in selected:
                to_remove.append(i)
        if to_remove:
            await container.remove_sample(to_remove)
        if selected:
            await container.add_sample(selected)

    @on(OptionList.OptionSelected, "#sample-list")
    async def select_sample_from_list(self, event: OptionList.OptionSelected):
        container = self.query_one("#condition-assignment", ConditionAssignment)
        await container.select_sample(event.option.prompt)

    @on(Input.Submitted, "#input-column-index")
    async def select_column_from_index(self, event: Input.Submitted):
        selection = self.query_one("#selection-list", SelectionList)
        data = event.value.replace('"', "").split("-")
        if len(data) == 1:
            if int(data[1]) == len(self.columns):
                self.notify("Index out of range.", severity="error")
                pass
            selection.select(self.columns[int(data[0])])
        elif len(data) == 2:
            if int(data[1]) == len(self.columns):
                self.notify("Index out of range.", severity="error")
                pass
            if int(data[0]) > int(data[1]):
                self.notify("Invalid range.", severity="error")
                pass
            for s in self.columns[int(data[0]):int(data[1])+1]:
                if s not in selection.selected:
                    selection.select(s)

    @on(Select.Changed, "#index-column-selection")
    async def update_index_summary(self, event: Select.Changed):
        print(event.value)
        index_count = len(self.df[event.value])
        unique_count = len(self.df[event.value].unique())
        unique = index_count == unique_count
        md = self.query_one("#index-summary", Markdown)
        await md.update(f"""
        Index Summary
        -------------
        1. Index column: {event.value}
        2. Total entries: {index_count}
        3. Is unique: {unique}""")

    async def action_submit_data(self):
        self.loading_indicator.remove_class("loading-indicator-inactive")
        self.loading_indicator.add_class("loading-indicator-active")
        selected = self.query_one("#selection-list", SelectionList).selected
        sample_dict = self.query_one("#condition-assignment", ConditionAssignment).sample_dict
        sample_cols = []
        for s in selected:
            if s in sample_dict:
                sample_cols.append({"name": s, "group": sample_dict[s]["group"]})
        temp = tempfile.NamedTemporaryFile(suffix=".tsv")
        self.df.fillna("").to_csv(temp, sep="\t", index=False)
        self.notify("Submitting data...", severity="information")
        async with httpx.AsyncClient() as client:
            try:
                req = await client.post(f"{protocol}://{host}:{port}/api/rawdata/", data={
                    "name": "",
                    "description": "",
                    "index_col": self.query_one("#index-column-selection", Select).value,
                    "sample_cols": json.dumps(sample_cols),
                    "metadata": json.dumps({}),
                    "file_type": "tsv",
                }, files={"file": ("file.tsv", temp)})
                if req.status_code == 201:
                    self.notify("Data submitted.", severity="information")
                else:
                    self.notify("Data submission failed.", severity="error")
            except Exception as e:
                self.notify("Data submission failed.", severity="error")
                logging.exception(e)
        self.loading_indicator.remove_class("loading-indicator-active")
        self.loading_indicator.add_class("loading-indicator-inactive")

    @on(Button.Pressed, "#auto-select-button")
    async def auto_select(self, event: Button.Pressed):
        try:
            result = await gpt_get_index(self.df.head(5))
            print(result)
            if result is not None:
                selection = self.query_one("#selection-list", SelectionList)
                for i in result:
                    if i in self.columns:
                        selection.select(i)
        except ValueError as e:
            self.notify("Auto select failed.", severity="error")
            logging.exception(e)

    async def action_directory_walk(self):
        def call_back_get_path(file_path: str) -> None:
            if file_path != "":
                self.turn_on_loading_indicator()
                self.directory_walk_path = file_path
                file_lists = []
                for root, dirs, files in os.walk(self.directory_walk_path):
                    for file in files:
                        if file.endswith(".csv") or file.endswith(".tsv") or file.endswith(".txt"):
                            file_lists.append(os.path.join(root, file))
                self.notify(f"Found eligible {len(file_lists)} files.", severity="information")
                if file_lists:
                    self.directory_walk_file_lists = file_lists
                self.turn_off_loading_indicator()
        await self.app.push_screen("directory_walk_upload", call_back_get_path)

    def turn_off_loading_indicator(self):
        self.query_one("#loading-indicator", LoadingIndicator).remove_class("loading-indicator-active")
        self.query_one("#loading-indicator", LoadingIndicator).add_class("loading-indicator-inactive")

    def turn_on_loading_indicator(self):
        self.query_one("#loading-indicator", LoadingIndicator).remove_class("loading-indicator-inactive")
        self.query_one("#loading-indicator", LoadingIndicator).add_class("loading-indicator-active")