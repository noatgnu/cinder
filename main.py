import json
import tempfile

import httpx
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, Markdown, Button, Static, SelectionList, Label, OptionList, Select
from textual.containers import Vertical, Horizontal, VerticalScroll, Container
import logging
import pandas as pd

from cinder.condition_assignment import ConditionAssignment


class Cinder(App):
    CSS_PATH = "main.tcss"
    BINDINGS = [
        Binding(key="ctrl+q", action="quit", description="Exit the application"),
        Binding(key="ctrl+s", action="submit_data", description="Submit data to server"),
    ]
    def compose(self) -> ComposeResult:
        yield Header(True, name="Cinder")
        yield Static("")
        yield Horizontal(
            Vertical(Input(placeholder="Filepath", id="input-file"), classes="column"),
            Button("Load", variant="primary", id="load-button"), id="file-input-section"
        )
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
                    Container(Label("Select index column"), id="index-column-selection-label"),
                    Vertical(

                        id="select-index-column-container"
                    ),
                    Container(Markdown("Index Summary", id="index-summary"), id="index-summary-container"),

                    id="column-selection",
                ),
                ConditionAssignment(id="condition-assignment"),
            )
        )
        yield Footer()

    def on_mount(self) -> None:
        self.screen.styles.background = "darkred"
        self.screen.styles.border = ("heavy", "white")
        condition_assignment = self.query_one("#condition-assignment", VerticalScroll)
        condition_assignment.border_title = "Assign Conditions"

    @on(Button.Pressed, "#load-button")
    async def load_file(self, event: Button.Pressed) -> None:
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
                req = await client.post("http://localhost:8000/api/rawdata/", data={
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


if __name__ == "__main__":
    logging.basicConfig(filename="cinder.log", level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    logging.log(logging.DEBUG, "Starting Cinder")
    app = Cinder()
    app.run()