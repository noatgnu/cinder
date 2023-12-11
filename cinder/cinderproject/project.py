import dataclasses
import json
import os

import click
import pandas as pd
from appdirs import AppDirs
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Grid, VerticalScroll, Vertical
from textual.widgets import Label, Header, Input, Placeholder, Button, OptionList, Footer, Markdown, Static, Select, \
    SelectionList
from textual.widgets.selection_list import Selection
from textual.widgets.option_list import Option

from cinder.base_screen import BaseScreen
from cinder.project import Project, QueryResult, ProjectDatabase
from cinder.utility import detect_delimiter_from_extension


class ModalUpdateTextScreen(BaseScreen):
    CSS_PATH = "modal_update_text_screen.tcss"

    def compose(self) -> ComposeResult:
        pass

    def on_mount(self) -> None:
        pass


class ProjectManagerScreen(BaseScreen):
    CSS_PATH = "project_manager_screen.tcss"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_list: list[Project] = []
        self.project: Project | None = None
        self.query: QueryResult | None = None

    def compose(self) -> ComposeResult:
        yield Header(True)
        yield Grid(
            Vertical(
                Input(),
                VerticalScroll(OptionList(id="project-selection-list"), id="project-selection-list-container"),
                Horizontal(id="pagination-container"), id="project-selection-container"),
            Vertical(Horizontal(Label("Select a project", id="project-name"), Button("Open project", "error", id="open-project", classes="button-hide"), classes="align-middle h-3"), VerticalScroll(Static(id="project-data"),id="project-data-container"), id="project-detail-container"),
            id="project-manager-grid")
        yield Footer()

    def on_mount(self) -> None:
        self.set_project_list_pagination()

    def set_project_list_pagination(self, offset=0, limit=10):
        self.query = self.app.db.search_projects(offset=offset, limit=limit)
        self.project_list = self.query.data
        self.query_one("#project-selection-list", OptionList).clear_options()
        for i in self.project_list:
            self.query_one("#project-selection-list", OptionList).add_option(Option(f"{i.project_id}. {i.project_name}", id=i.project_id))
        pagination = self.query_one("#pagination-container", Horizontal)
        pagination.remove_children()
        left_button = Button("<", "error", id="pagination-left", classes="pagination-button")
        right_button = Button(">", "error", id="pagination-right", classes="pagination-button")
        # disable left button if offset is 0
        if self.query.offset == 0:
            left_button.disabled = True
        # disable right button if offset + limit is greater than total
        if self.query.offset + self.query.limit >= self.query.total:
            right_button.disabled = True
        total_pages = self.query.total // self.query.limit
        if self.query.total % self.query.limit != 0:
            total_pages += 1
        current_page_number = self.query.offset // self.query.limit + 1
        current_page = Label(f"Page {current_page_number} of {total_pages}", id="pagination-label")
        pagination.mount(left_button, current_page, right_button)

    @on(Button.Pressed, "#pagination-left")
    async def pagination_left(self, event):
        self.set_project_list_pagination(offset=self.query.offset - self.query.limit)

    @on(Button.Pressed, "#pagination-right")
    async def pagination_right(self, event):
        self.set_project_list_pagination(offset=self.query.offset + self.query.limit)

    @on(OptionList.OptionSelected, "#project-selection-list")
    async def project_selected(self, event: OptionList.OptionSelected):
        self.project: Project = self.app.db.get_project(project_id=event.option.id)
        self.notify(f"Selected {self.project.project_name}")
        project_label = self.query_one("#project-name", Label)
        project_label.update(self.project.project_name)
        project_data = self.query_one("#project-data", Static)
        project_data.update(f"""{self.project.description}""")
        button = self.query_one("#open-project", Button)
        button.remove_class("button-hide")

    @on(Button.Pressed, "#open-project")
    async def open_project(self, event):
        if self.project:
            self.app.data = self.project
            await self.app.push_screen("project_screen")


class ProjectScreen(BaseScreen):
    CSS_PATH = "project_screen.tcss"
    BINDINGS = [
        Binding("ctrl+r", "refresh", "Refresh project data"),
        Binding("ctrl+s", "save", "Save project data")
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unprocessed_df: pd.DataFrame | None = None
        self.annotation_df: pd.DataFrame | None = None
        self.comparison_matrix_df: pd.DataFrame | None = None
        self.selected_unprocessed_file: str | None = None
        self.selected_sample_annotation_file: str | None = None
        self.selected_comparison_matrix_file: str | None = None
        self.index_column: str | None = None
        self.meta_data_columns: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(True, name="Cinder")
        yield Horizontal(Label("Project name"), Input(value=self.app.data.project_name), classes="align-middle",
                         id="project-screen-title")
        yield Grid(
            Vertical(Horizontal(Label("Unprocessed Files"), classes="align-middle h-1"),
                     VerticalScroll(
                         OptionList(*[Option(i[1]["filename"], id=str(i[0])) for i in enumerate(self.app.data.unprocessed)],
                                    id="unprocessed-file-selection"),
                         id="unprocessed-file-scroll", classes="file-display-scroll-project ml-4"
                     ),
                     Markdown("# Select an unprocessed file", id="unprocessed-file-markdown"),
                     Select(options=[], id="index-column-selection", prompt="Select index column", classes="ml-4"),
                        SelectionList(*[], id="additional-meta-index-columns", classes="ml-4")
                     ),
            Vertical(Horizontal(Label("Sample Annotation Files"), classes="align-middle h-1"),
                     VerticalScroll(
                         OptionList(*[Option(i[1]["filename"], id=str(i[0])) for i in enumerate(self.app.data.sample_annotation)],
                                    id="sample-annotation-file-selection"),
                         id="sample-annotation-file-scroll", classes="file-display-scroll-project ml-4"
                     ), Markdown("# Select an annotation file", id="sample-annotation-file-markdown"), ),
            Vertical(Horizontal(Label("Comparison Matrix Files"), classes="align-middle h-1"),
                     VerticalScroll(
                         OptionList(*[Option(i[1]["filename"], id=str(i[0])) for i in enumerate(self.app.data.comparison_matrix)],
                                    id="comparison-matrix-file-selection"),
                         id="comparison-matrix-file-scroll", classes="file-display-scroll-project ml-4"
                     ), Markdown("# Select a comparison matrix file", id="comparison-matrix-file-markdown"), ),

            id="project-screen-grid",
        )
        yield Footer()

    def on_mount(self) -> None:
        pass

    @on(SelectionList.OptionSelected, "#additional-meta-index-columns")
    async def additional_meta_index_columns_selected(self, event):
        if self.unprocessed_df is not None:
            self.meta_data_columns = event

    @on(Select.Changed, "#index-column-selection")
    async def index_column_selected(self, event):
        if self.unprocessed_df is not None:
            self.notify(f"Selected {event.value} as index column")
            markdown = self.query_one("#unprocessed-file-markdown", Markdown)
            markdown_text = f"""# {self.selected_unprocessed_file}
                    - rows: {self.unprocessed_df.shape[0]}
                    - columns: {self.unprocessed_df.shape[1]}
                    - index column: {event.value}
                    """
            await markdown.update(markdown_text)
    @on(OptionList.OptionSelected, "#unprocessed-file-selection")
    async def unprocessed_file_selected(self, event: OptionList.OptionSelected):
        self.selected_unprocessed_file = self.app.data.unprocessed[int(event.option.id)]
        print(self.selected_unprocessed_file)
        self.unprocessed_df = pd.read_csv(
            os.path.join(
                self.app.data.project_data_path,
                os.sep.join(self.selected_unprocessed_file["path"]),
                self.selected_unprocessed_file["filename"]),
            sep=detect_delimiter_from_extension(self.selected_unprocessed_file["filename"])
        )
        index_selection = self.query_one("#index-column-selection", Select)
        index_selection.set_options([(i, i) for i in self.unprocessed_df.columns])
        additional_meta_index_columns = self.query_one("#additional-meta-index-columns", SelectionList)
        additional_meta_index_columns.clear_options()
        additional_meta_index_columns.add_options([Selection(i, i) for i in self.unprocessed_df.columns])
        json_path = [self.app.data.project_data_path] + self.selected_unprocessed_file["path"] + [self.selected_unprocessed_file["filename"] + ".json"]
        json_path = os.path.join(*json_path)
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                settings = json.load(f)
                index_column = settings["index_column"]
                index_selection.value = index_column
                meta_data_columns = settings["meta_data_columns"]
                for i in meta_data_columns:
                    additional_meta_index_columns.select(i)


        markdown = self.query_one("#unprocessed-file-markdown", Markdown)
        markdown_text = f"""# {event.option.prompt}
        - rows: {self.unprocessed_df.shape[0]}
        - columns: {self.unprocessed_df.shape[1]}
        - index column: {index_selection.value}
        """
        await markdown.update(markdown_text)
        markdown.refresh()
        self.notify(f"Selected {event.option.prompt}")

    @on(OptionList.OptionSelected, "#sample-annotation-file-selection")
    async def sample_annotation_file_selected(self, event):
        self.selected_sample_annotation_file = self.app.data.sample_annotation[int(event.option.id)]
        self.annotation_df = pd.read_csv(
            os.path.join(
                self.app.data.project_data_path,
                os.sep.join(self.selected_sample_annotation_file["path"]),
                self.selected_sample_annotation_file["filename"]),
            sep=detect_delimiter_from_extension(self.selected_sample_annotation_file["filename"])
        )
        markdown = self.query_one("#sample-annotation-file-markdown", Markdown)
        markdown_text = f"""# {event.option.prompt}
        - unique groups: {len(self.annotation_df["condition"].unique())}
        - samples: {len(self.annotation_df["sample"].unique())}
        """
        await markdown.update(markdown_text)
        self.notify(f"Selected {event.option.prompt}")

    @on(OptionList.OptionSelected, "#comparison-matrix-file-selection")
    async def comparison_matrix_file_selected(self, event):
        self.selected_comparison_matrix_file = self.app.data.comparison_matrix[int(event.option.id)]
        self.comparison_matrix_df = pd.read_csv(
            os.path.join(
                self.app.data.project_data_path,
                os.sep.join(self.selected_comparison_matrix_file["path"]),
                self.selected_comparison_matrix_file["filename"]),
            sep=detect_delimiter_from_extension(self.selected_comparison_matrix_file["filename"])
        )
        markdown = self.query_one("#comparison-matrix-file-markdown", Markdown)
        markdown_text = f"""# {event.option.prompt}
        - comparisons: {len(self.comparison_matrix_df["comparison_label"].unique())}
        """
        await markdown.update(markdown_text)
        self.notify(f"Selected {event.option.prompt}")

    @on(Button.Pressed, "#add-unprocessed-file")
    async def add_unprocessed_file(self, event):
        await self.query_one("#unprocessed-file-scroll", VerticalScroll).mount(Input(value="", classes="small-input"))
        self.notify("Added unprocessed file")

    async def action_refresh(self):
        self.app.data.refresh()
        self.notify("Refreshed project data")
        # update the unprocessed file list widget, sample annotation file list widget, and comparison matrix file list widget
        unprocessed = self.query_one("#unprocessed-file-selection", OptionList)
        unprocessed.clear_options()
        unprocessed.add_options([Option(i, id=i) for i in self.app.data.unprocessed])
        sample_annotation = self.query_one("#sample-annotation-file-selection", OptionList)
        sample_annotation.clear_options()
        sample_annotation.add_options([Option(i, id=i) for i in self.app.data.sample_annotation])
        comparison_matrix = self.query_one("#comparison-matrix-file-selection", OptionList)
        comparison_matrix.clear_options()
        comparison_matrix.add_options([Option(i, id=i) for i in self.app.data.comparison_matrix])

    async def action_save(self):
        # save the project data to the project.json file
        self.app.data.refresh()
        with open(os.path.join(self.app.data.project_path, "project.sha1"), "rt") as f:
            sha1 = f.read()
        if self.app.data.project_id == 0:

            result = self.app.db.create_project(name=self.app.data.project_name, description=self.app.data.description, location=self.app.data.project_path, hash=sha1)
            self.app.data.project_id = result["id"]
            self.app.data.project_global_id = result["global_id"]
        else:
            self.app.db.update_project(project_id=self.app.data.project_id, name=self.app.data.project_name, description=self.app.data.description, location=self.app.data.project_path, hash=sha1)

        with open(os.path.join(self.app.data.project_path, "project.json"), "w") as f:
            json.dump(dataclasses.asdict(self.app.data), f, indent=2)
        with open(
                os.path.join(self.app.data.project_data_path, "unprocessed", f"{self.selected_unprocessed_file}.json"),
                "w") as f:
            json.dump({"index_column": self.index_column, "meta_data_columns": self.meta_data_columns}, f)
        self.notify("Saved project data")


class CinderProject(App):
    SCREENS = {"project_screen": ProjectScreen()}
    TITLE = "Cinder Project Manager"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = Project(project_name="", project_path="", project_data_path="", project_metadata={}, unprocessed=[],
                            differential_analysis=[], sample_annotation=[], other_files=[], comparison_matrix=[], project_id=0, project_global_id="", description="")

    def on_mount(self) -> None:
        self.push_screen("project_screen")


@click.command()
@click.argument("project_name", type=click.Path(exists=False), default="")
def manage_project(project_name: str):
    """Create a project folder and create configuration file from project dictionary"""


    if not os.path.exists(project_name):
        os.mkdir(project_name)


    else:
        print("Project folder already exists")

    if project_name != "":
        project_folder = os.path.abspath(project_name)
        if not os.path.exists(os.path.join(project_folder, "project.json")):

            os.makedirs(os.path.join(project_name, "data"), exist_ok=True)
            os.makedirs(os.path.join(project_name, "data", "unprocessed"), exist_ok=True)
            os.makedirs(os.path.join(project_name, "data", "differential_analysis"), exist_ok=True)
            os.makedirs(os.path.join(project_name, "data", "sample_annotation"), exist_ok=True)
            os.makedirs(os.path.join(project_name, "data", "other_files"), exist_ok=True)
            os.makedirs(os.path.join(project_name, "data", "comparison_matrix"), exist_ok=True)
            project = Project(
                project_id=0,
                project_name=project_name,
                project_path=os.path.abspath(project_name),
                project_data_path=os.path.abspath(os.path.join(project_name, "data")),
                project_metadata={},
                unprocessed=[],
                differential_analysis=[],
                sample_annotation=[],
                other_files=[],
                comparison_matrix=[],
                project_global_id="",
                description=""
            )

            with open(project_name + "/project.json", "w") as f:
                json.dump(dataclasses.asdict(project), f, indent=2)
        else:
            with open(os.path.join(project_folder, "project.json"), "r") as f:
                project_dict = json.load(f)
                project = Project(**project_dict)
    else:
        if os.path.exists("project.json"):
            with open("project.json", "r") as f:
                project_dict = json.load(f)
                project = Project(**project_dict)
        else:
            raise FileNotFoundError("No project.json file found")
    project.refresh()
    app = CinderProject()
    app.data = project
    print(app.data)
    app_dir = AppDirs("Cinder", "Cinder")
    os.makedirs(app_dir.user_config_dir, exist_ok=True)
    app.config_dir = app_dir
    if os.path.exists(os.path.join(app_dir.user_config_dir, "data_manager_config.json")):
        with open(os.path.join(app_dir.user_config_dir, "data_manager_config.json"), "r") as f:
            app.config = json.load(f)
    else:
        app.config = {"central_rest_api": {
            "host": "localhost",
            "port": 80,
            "protocol": "http"
        }}
        with open(os.path.join(app_dir.user_config_dir, "data_manager_config.json"), "w") as f:
            json.dump(app.config, f)

    app.db = ProjectDatabase(os.path.join(app_dir.user_config_dir, "data_manager.db"))
    app.run()
