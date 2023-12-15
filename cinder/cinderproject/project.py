import dataclasses
import json
import os
from io import BytesIO

import click
import httpx
import pandas as pd
from textual_plotext import PlotextPlot
from cinder.util_screen.modal_quit import ModalQuitScreen
from cinder.utils.common import app_dir, load_settings, ProjectFile, Project, QueryResult, ProjectDatabase, CorpusServer
from textual import on, events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Grid, VerticalScroll, Vertical
from textual.screen import Screen
from textual.widgets import Label, Header, Input, Placeholder, Button, OptionList, Footer, Markdown, Static, Select, \
    SelectionList, TabbedContent, TabPane, TextArea, Checkbox
from textual.widgets.selection_list import Selection
from textual.widgets.option_list import Option

from cinder.base_screen import BaseScreen
from cinder.utility import detect_delimiter_from_extension


class Barchart(PlotextPlot):
    def __init__(
            self,
            title: str,
            *,
            name: str | None = None,
            id: str | None = None,  # pylint:disable=redefined-builtin
            classes: str | None = None,
            disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._title = title


    def on_mount(self):
        self.plt.xlabel("Sample")
        self.plt.theme('serious')
        self.styles.background = "black"
        self.styles.border = ("heavy", "white")

    def draw(self, x: list[str|int], y: list[float|int]):
        self.plt.clear_data()

        self.plt.bar(x, y, width=0.001)
        self.refresh()

    def set_title(self, title: str):
        self.plt.title(title)
        self.refresh()

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
        Binding("ctrl+s", "save", "Save project data"),
        Binding("ctrl+r", "save_to_server", "Save project data to server"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_df_dict: dict[str, pd.DataFrame|None] = {}

        self.project_selected_file_dict: dict[str, ProjectFile|None] = {}

        self.index_column: str | None = None
        self.meta_data_columns: list[str] = []
        self.current_tab: str = "unprocessed"
        self.selected_index_value_dict: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Header(True, name="Cinder")
        yield Horizontal(Label("Project name"), Input(value=self.app.data.project_name), classes="align-middle",
                         id="project-screen-title")

        with TabbedContent(*self.app.data.project_files.keys(), initial=self.current_tab, id="project-screen-tabs"):
            for i in self.app.data.project_files.keys():
                with TabPane(i, id=i):
                    yield Grid(classes="tabbed-content-grid", id=f"{i}-grid")


        # yield Grid(
        #     Vertical(Horizontal(Label("Unprocessed Files"), classes="align-middle h-1"),
        #              VerticalScroll(
        #                  OptionList(*[Option(i[1].filename, id=str(i[0])) for i in enumerate(self.app.data.project_files["unprocessed"]) if not i[1].filename.endswith(".json")],
        #                             id="unprocessed-file-selection"),
        #                  id="unprocessed-file-scroll", classes="file-display-scroll-project ml-4"
        #              ),VerticalScroll(Markdown("# Select an unprocessed file", id="unprocessed-file-markdown"))
        #              ,
        #              ),
        #     Vertical(Horizontal(Label("Searched Files"), classes="align-middle h-1"),
        #              VerticalScroll(
        #                  OptionList(*[Option(i[1].filename, id=str(i[0])) for i in
        #                               enumerate(self.app.data.project_files["searched"]) if
        #                               not i[1].filename.endswith(".json")],
        #                             id="searched-file-selection"),
        #                  id="searched-file-scroll", classes="file-display-scroll-project ml-4"
        #              ),VerticalScroll(Markdown("# Select a searched file", id="searched-file-markdown"),
        #              Select(options=[], id="searched-index-column-selection", prompt="Select index column", classes="ml-4"),
        #              SelectionList(*[], id="searched-additional-meta-index-columns", classes="ml-4"))
        #              ),
        #     Vertical(Horizontal(Label("Differential Analysis Files"), classes="align-middle h-1"),
        #              VerticalScroll(
        #                  OptionList(*[Option(i[1].filename, id=str(i[0])) for i in
        #                               enumerate(self.app.data.project_files["differential_analysis"]) if
        #                               not i[1].filename.endswith(".json")],
        #                             id="differential-analysis-file-selection"),
        #                  id="differential-analysis-file-scroll", classes="file-display-scroll-project ml-4"
        #              ), VerticalScroll(Markdown("# Select a differential analysis file", id="differential-analysis-file-markdown"),
        #              Select(options=[], id="differential-analysis-index-column-selection", prompt="Select index column",
        #                     classes="ml-4"),
        #              SelectionList(*[], id="differential-analysis-additional-meta-index-columns", classes="ml-4"))
        #
        #              ),
        #     Vertical(Horizontal(Label("Sample Annotation Files"), classes="align-middle h-1"),
        #              VerticalScroll(
        #                  OptionList(*[Option(i[1].filename, id=str(i[0])) for i in enumerate(self.app.data.project_files["sample_annotation"]) if not i[1].filename.endswith(".json")],
        #                             id="sample-annotation-file-selection"),
        #                  id="sample-annotation-file-scroll", classes="file-display-scroll-project ml-4"
        #              ), VerticalScroll(Markdown("# Select an annotation file", id="sample-annotation-file-markdown")), ),
        #     Vertical(Horizontal(Label("Comparison Matrix Files"), classes="align-middle h-1"),
        #              VerticalScroll(
        #                  OptionList(*[Option(i[1].filename, id=str(i[0])) for i in enumerate(self.app.data.project_files["comparison_matrix"]) if not i[1].filename.endswith(".json")],
        #                             id="comparison-matrix-file-selection"),
        #                  id="comparison-matrix-file-scroll", classes="file-display-scroll-project ml-4"
        #              ), VerticalScroll(Markdown("# Select a comparison matrix file", id="comparison-matrix-file-markdown")), ),
        #
        #
        #     id="project-screen-grid",
        # )
        yield Footer()

    def on_mount(self) -> None:
        for i in self.app.config["project_folders"]:
            self.project_df_dict[i] = None
            self.project_selected_file_dict[i] = None
        self.activate_tab()

    def activate_tab(self):

        grid = self.query_one(f"#{self.current_tab}-grid", Grid)
        # check if grid has children
        if len(grid.children) == 0:
            grid.mount(*[VerticalScroll(OptionList(
                *[Option(i2[1].filename, id=str(i2[0])) for i2 in enumerate(self.app.data.project_files[self.current_tab])
                  if
                  not i2[1].filename.endswith(".json")], id=f"{self.current_tab}-file-selection"), id=f"file-scroll",
                classes="file-display-scroll-project ml-4 row-span-3"),
                Vertical(
                    Label("Selected File: None", id=f"{self.current_tab}-selected-file-label"),
                    Horizontal(
                        Button("Load", id=f"{self.current_tab}-load-file", variant="primary"),
                        Checkbox("Enable remote save", id=f"{self.current_tab}-enable-save", value=True),
                    ),
                ), VerticalScroll(
                    Label("Description"),
                    TextArea(id=f"{self.current_tab}-file-description"),
                    classes="border-white"
                )])
            if self.current_tab != "differential_analysis":

                grid.mount(*[Vertical(
                    Label("Select index column"),
                    Select(options=[], id=f"{self.current_tab}-index-column-selection", prompt="Select index column",
                           classes="ml-4"), ),
                    Vertical(
                        Label("Select additional meta index columns"),
                        VerticalScroll(
                            SelectionList(*[], id=f"{self.current_tab}-additional-meta-index-columns", classes="ml-4"), )),
                    Vertical(
                        Label("Select sample columns"),
                        VerticalScroll(SelectionList(*[], id=f"{self.current_tab}-sample-columns", classes="ml-4"), )
                    ),
                    Horizontal(Select(options=[], id=f"{self.current_tab}-index-value-selection", prompt="Select index value",
                               classes="ml-4"),Button("View Plot", id=f"{self.current_tab}-view-plot", variant="primary", classes="ml-4")),
                    Barchart("Bar Plot", id=f"{self.current_tab}-plot", classes="row-span-2 col-span-3")
                    #PlotextPlot(id=f"{self.current_tab}-plot", classes="row-span-2 col-span-2")
                ])
            else:
                grid.mount(*[Vertical(
                    Label("Select index column"),
                    Select(options=[], id=f"{self.current_tab}-index-column-selection", prompt="Select index column",
                           classes="ml-4"), ),
                    Vertical(
                        Label("Select FoldChange Column"),
                        Checkbox("Log2 Transform", id=f"{self.current_tab}-log2-fold-change", value=False),
                        VerticalScroll(SelectionList(*[], id=f"{self.current_tab}-fold-change", classes="ml-4"), )
                    ),
                    Vertical(
                        Label("Select p-value Column"),
                        Checkbox("-Log10 Transform", id=f"{self.current_tab}-log10-p-value", value=False),
                        VerticalScroll(SelectionList(*[], id=f"{self.current_tab}-p-value", classes="ml-4"), )),
                    Horizontal(
                        Select(options=[], id=f"{self.current_tab}-index-value-selection", prompt="Select index value",
                               classes="ml-4"),
                        Button("View Plot", id=f"{self.current_tab}-view-plot", variant="primary", classes="ml-4"),
                    ),

                    PlotextPlot(id=f"{self.current_tab}-plot", classes="row-span-2 col-span-3")
                ])

    @on(TabbedContent.TabActivated, "#project-screen-tabs")
    async def tab_activated(self, event: TabbedContent.TabActivated):
        self.current_tab = event.tab.id
        print(self.current_tab)
        self.activate_tab()

    @on(OptionList.OptionSelected)
    async def file_selected(self, event: OptionList.OptionSelected):
        if event.option.id is not None:
            current_file_label = self.query_one(f"#{self.current_tab}-selected-file-label", Label)
            current_file_label.update(f"Selected File: {event.option.prompt}")
            self.project_selected_file_dict[self.current_tab] = self.app.data.project_files[self.current_tab][int(event.option.id)]

    @on(Button.Pressed)
    async def button_action(self, event: Button.Pressed):
        if event.button.id is not None:
            if event.button.id.endswith("view-plot"):
                plot = self.query_one(f"#{self.current_tab}-plot", Barchart)
                if self.current_tab != "differential_analysis":
                    df = self.project_df_dict[self.current_tab]
                    index_column = self.query_one(f"#{self.current_tab}-index-column-selection", Select).value
                    samples = self.query_one(f"#{self.current_tab}-sample-columns", SelectionList).selected
                    index_value = self.selected_index_value_dict[self.current_tab]
                    data = list(df[df[index_column] == index_value][samples].fillna(0).astype(float).values[0])
                    plot.draw(samples, data)
                    plot.set_title("Data distribution for " + index_value)
            else:
                delimiter = detect_delimiter_from_extension(self.project_selected_file_dict[self.current_tab].filename)
                if delimiter:
                    self.project_df_dict[self.current_tab] = pd.read_csv(
                        os.path.join(
                            self.app.data.project_data_path,
                            *self.project_selected_file_dict[self.current_tab].path,
                            self.project_selected_file_dict[self.current_tab].filename),
                        sep=delimiter
                    )
                    index_selection = self.query_one(f"#{self.current_tab}-index-column-selection", Select)
                    index_selection.set_options([(i, i) for i in self.project_df_dict[self.current_tab].columns])
                    additional_meta_index_columns = self.query_one(f"#{self.current_tab}-additional-meta-index-columns", SelectionList)
                    additional_meta_index_columns.clear_options()
                    additional_meta_index_columns.add_options([Selection(i, i) for i in self.project_df_dict[self.current_tab].columns])
                    if self.current_tab != "differential_analysis":
                        sample_columns = self.query_one(f"#{self.current_tab}-sample-columns", SelectionList)
                        sample_columns.clear_options()
                        sample_columns.add_options([Selection(i, i) for i in self.project_df_dict[self.current_tab].columns])
                    self.notify("Loaded " + self.project_selected_file_dict[self.current_tab].filename)
                else:
                    self.notify("File can only be in csv, tsv, or txt format")

    @on(Select.Changed)
    async def index_column_selected(self, event: Select.Changed):
        if event.select.id is not None:
            if event.select.id.endswith("index-column-selection"):
                index_value_selection = self.query_one(f"#{self.current_tab}-index-value-selection", Select)
                index_value_selection.set_options([(i, i) for i in self.project_df_dict[self.current_tab][event.select.value]])
            else:
                self.selected_index_value_dict[self.current_tab] = event.select.value


    @on(SelectionList.OptionSelected, "#additional-meta-index-columns")
    async def additional_meta_index_columns_selected(self, event):
        if self.project_df_dict["unprocessed"] is not None:
            self.meta_data_columns = event

    @on(Select.Changed, "#searched-index-column-selection")
    async def searched_index_column_selected(self, event):
        if self.project_df_dict["searched"] is not None:
            self.notify(f"Selected {event.value} as index column")
            markdown = self.query_one("#searched-file-markdown", Markdown)
            markdown_text = f"""# {self.project_selected_file_dict["searched"].filename}
- rows: {self.project_df_dict["searched"].shape[0]}
- columns: {self.project_df_dict["searched"].shape[1]}
- index column: {event.value}
                    """
            await markdown.update(markdown_text)

    @on(Select.Changed, "#differential-analysis-index-column-selection")
    async def differential_analysis_index_column_selected(self, event):
        if self.project_df_dict["differential_analysis"] is not None:
            self.notify(f"Selected {event.value} as index column")
            markdown = self.query_one("#differential-analysis-file-markdown", Markdown)
            markdown_text = f"""# {self.project_selected_file_dict["differential_analysis"].filename}
- rows: {self.project_df_dict["differential_analysis"].shape[0]}
- columns: {self.project_df_dict["differential_analysis"].shape[1]}
- index column: {event.value}
                        """
            await markdown.update(markdown_text)

    @on(OptionList.OptionSelected, "#differential-analysis-file-selection")
    async def differential_analysis_file_selected(self, event: OptionList.OptionSelected):
        self.project_selected_file_dict["differential_analysis"] = self.app.data.project_files["differential_analysis"][int(event.option.id)]
        self.project_df_dict["differential_analysis"] = pd.read_csv(
            os.path.join(
                self.app.data.project_data_path,
                *self.project_selected_file_dict["differential_analysis"].path,
                self.project_selected_file_dict["differential_analysis"].filename),
            sep=detect_delimiter_from_extension(self.project_selected_file_dict["differential_analysis"].filename)
        )
        index_selection = self.query_one("#differential-analysis-index-column-selection", Select)
        index_selection.set_options([(i, i) for i in self.project_df_dict["differential_analysis"].columns])
        additional_meta_index_columns = self.query_one("#searched-additional-meta-index-columns", SelectionList)
        additional_meta_index_columns.clear_options()
        additional_meta_index_columns.add_options([Selection(i, i) for i in self.project_df_dict["differential_analysis"].columns])
        json_path = [self.app.data.project_data_path] + list(self.project_selected_file_dict["differential_analysis"].path) + [
            self.project_selected_file_dict["differential_analysis"].filename + ".json"]
        json_path = os.path.join(*json_path)
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                settings = json.load(f)
                index_column = settings["index_column"]
                index_selection.value = index_column
                meta_data_columns = settings["meta_data_columns"]
                for i in meta_data_columns:
                    additional_meta_index_columns.select(i)

        markdown = self.query_one("#differential-analysis-file-markdown", Markdown)
        markdown_text = f"""# {event.option.prompt}
- rows: {self.project_df_dict["searched"].shape[0]}
- columns: {self.project_df_dict["searched"].shape[1]}
            """
        await markdown.update(markdown_text)
        markdown.refresh()
        self.notify(f"Selected {event.option.prompt}")

    @on(OptionList.OptionSelected, "#searched-file-selection")
    async def searched_file_selected(self, event: OptionList.OptionSelected):
        self.project_selected_file_dict["searched"] = self.app.data.project_files["searched"][int(event.option.id)]
        self.project_df_dict["searched"] = pd.read_csv(
            os.path.join(
                self.app.data.project_data_path,
                *self.project_selected_file_dict["searched"].path,
                self.project_selected_file_dict["searched"].filename),
            sep=detect_delimiter_from_extension(self.project_selected_file_dict["searched"].filename)
        )
        index_selection = self.query_one("#searched-index-column-selection", Select)
        index_selection.set_options([(i, i) for i in self.project_df_dict["searched"].columns])
        additional_meta_index_columns = self.query_one("#searched-additional-meta-index-columns", SelectionList)
        additional_meta_index_columns.clear_options()
        additional_meta_index_columns.add_options([Selection(i, i) for i in self.project_df_dict["searched"].columns])
        json_path = [self.app.data.project_data_path] + list(self.project_selected_file_dict["searched"].path) + [self.project_selected_file_dict["searched"].filename + ".json"]
        json_path = os.path.join(*json_path)
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                settings = json.load(f)
                index_column = settings["index_column"]
                index_selection.value = index_column
                meta_data_columns = settings["meta_data_columns"]
                for i in meta_data_columns:
                    additional_meta_index_columns.select(i)


        markdown = self.query_one("#searched-file-markdown", Markdown)
        markdown_text = f"""# {event.option.prompt}
- rows: {self.project_df_dict["searched"].shape[0]}
- columns: {self.project_df_dict["searched"].shape[1]}
        """
        await markdown.update(markdown_text)
        markdown.refresh()
        self.notify(f"Selected {event.option.prompt}")

    @on(OptionList.OptionSelected, "#sample-annotation-file-selection")
    async def sample_annotation_file_selected(self, event):
        self.project_selected_file_dict["sample_annotation"] = self.app.data.project_files["sample_annotation"][int(event.option.id)]
        self.project_df_dict["sample_annotation"] = pd.read_csv(
            os.path.join(
                self.app.data.project_data_path,
                os.sep.join(self.project_selected_file_dict["sample_annotation"].path),
                self.project_selected_file_dict["sample_annotation"].filename),
            sep=detect_delimiter_from_extension(self.project_selected_file_dict["sample_annotation"].filename)
        )
        markdown = self.query_one("#sample-annotation-file-markdown", Markdown)
        markdown_text = f"""# {event.option.prompt}
- unique groups: {len(self.project_df_dict["sample_annotation"]["condition"].unique())}
- samples: {len(self.project_df_dict["sample_annotation"]["sample"].unique())}
        """
        await markdown.update(markdown_text)
        self.notify(f"Selected {event.option.prompt}")

    @on(OptionList.OptionSelected, "#comparison-matrix-file-selection")
    async def comparison_matrix_file_selected(self, event):
        self.project_selected_file_dict["comparison_matrix"] = self.app.data.project_files["comparison_matrix"][int(event.option.id)]
        self.project_df_dict["comparison_matrix"] = pd.read_csv(
            os.path.join(
                self.app.data.project_data_path,
                os.sep.join(self.project_selected_file_dict["comparison_matrix"].path),
                self.project_selected_file_dict["comparison_matrix"].filename),
            sep=detect_delimiter_from_extension(self.project_selected_file_dict["comparison_matrix"].filename)
        )
        markdown = self.query_one("#comparison-matrix-file-markdown", Markdown)
        markdown_text = f"""# {event.option.prompt}
- comparisons: {len(self.project_df_dict["comparison_matrix"]["comparison_label"].unique())}
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
        searched = self.query_one("#searched-file-selection", OptionList)
        searched.clear_options()
        searched.add_options([Option(i[1].filename, id=str(i[0])) for i in enumerate(self.app.data.project_files["searched"])])
        unprocessed = self.query_one("#unprocessed-file-selection", OptionList)
        unprocessed.clear_options()
        unprocessed.add_options([Option(i[1].filename, id=str(i[0])) for i in enumerate(self.app.data.project_files["unprocessed"])])
        sample_annotation = self.query_one("#sample-annotation-file-selection", OptionList)
        sample_annotation.clear_options()
        sample_annotation.add_options([Option(i[1].filename, id=str(i[0])) for i in enumerate(self.app.data.project_files["sample_annotation"])])
        comparison_matrix = self.query_one("#comparison-matrix-file-selection", OptionList)
        comparison_matrix.clear_options()
        comparison_matrix.add_options([Option(i[1].filename, id=str(i[0])) for i in enumerate(self.app.data.project_files["comparison_matrix"])])
        differential_analysis = self.query_one("#differential-analysis-file-selection", OptionList)
        differential_analysis.clear_options()
        differential_analysis.add_options([Option(i[1].filename, id=str(i[0])) for i in enumerate(self.app.data.project_files["differential_analysis"])])

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
            json.dump(self.app.data.to_dict(), f, indent=2)
        if self.project_selected_file_dict["unprocessed"] is not None:
            with open(
                    os.path.join(self.app.data.project_data_path, "unprocessed", f"{self.project_selected_file_dict['unprocessed'].filename}.json"),
                    "w") as f:
                json.dump({"index_column": self.index_column, "meta_data_columns": self.meta_data_columns}, f)
        self.notify("Saved project data")

    async def action_save_to_server(self):
        await self.action_save()
        host = f"{self.app.config['central_rest_api']['protocol']}://{self.app.config['central_rest_api']['host']}:{self.app.config['central_rest_api']['port']}"
        corpus = CorpusServer(host, self.app.config["central_rest_api"]["api_key"], self.app.db)
        if self.app.data.remote_id:
            await corpus.update_project(self.app.data)
        else:
            await corpus.create_project(self.app.data)
        async for file in corpus.upload_file(self.app.data):
            self.notify(f"Uploaded {file.filename}")
        self.app.data.refresh()
        await self.action_save()
        await corpus.update_project(self.app.data)

        self.notify("Saved project data to server")

class CinderProject(App):
    SCREENS = {"project_screen": ProjectScreen(), "modal_quit": ModalQuitScreen(), "project_manager_screen": ProjectManagerScreen()}
    TITLE = "Cinder Project Manager"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = Project(project_name="", project_path="", project_data_path="", project_files={}, project_metadata={}, project_id=0, project_global_id="", description="")

    def on_mount(self) -> None:
        self.push_screen("project_screen")


@click.command()
@click.argument("project_name", type=click.Path(exists=False), default="")
def manage_project(project_name: str):
    """Create a project folder and create configuration file from project dictionary"""
    os.makedirs(app_dir.user_config_dir, exist_ok=True)
    settings = load_settings()
    if not os.path.exists(project_name):
        os.mkdir(project_name)

    else:
        print("Project folder already exists")

    if project_name != "":
        project_folder = os.path.abspath(project_name)
        if not os.path.exists(os.path.join(project_folder, "project.json")):

            os.makedirs(os.path.join(project_name, "data"), exist_ok=True)
            for i in settings["project_folders"]:
                os.makedirs(os.path.join(project_name, "data", i), exist_ok=True)
            project = Project(
                project_id=0,
                project_name=project_name,
                project_path=os.path.abspath(project_name),
                project_data_path=os.path.abspath(os.path.join(project_name, "data")),
                project_files={i: [] for i in settings["project_folders"]},
                project_metadata={},
                project_global_id="",
                description=""
            )

            with open(project_name + "/project.json", "w") as f:
                json.dump(project.to_dict(), f, indent=2)
        else:
            with open(os.path.join(project_folder, "project.json"), "r") as f:
                project_dict = json.load(f)
                for i in settings["project_folders"]:
                    for i2, f in enumerate(project_dict["project_files"][i]):
                        project_dict["project_files"][i][i2] = ProjectFile(**f)
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


    app.config_dir = app_dir
    app.config = settings

    app.db = ProjectDatabase(os.path.join(app_dir.user_config_dir, "data_manager.db"))
    app.run()
