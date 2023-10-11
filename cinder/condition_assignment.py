import logging
from typing import List

from textual import events, on
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal, Vertical, Container
from textual.widgets import Input, Static, Label, OptionList


class ConditionAssignment(VerticalScroll):
    CSS_PATH = "condition_assignment.tcss"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border = ("heavy", "white")
        self.border_title = "Assign Conditions"
        self.sample_dict = {}
        self.selected_sample = ""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Container(Label("Group assignment for selected sample", id="sample-label"), id="sample-label-container"),
            Horizontal(VerticalScroll(
                OptionList(id="sample-list"), id="sample-list-container"
            ), Horizontal(
                Input(placeholder="group name", id="group-name-input"),
            ), id="sample-list-section")
        )

    async def add_sample(self, samples: List[str]):
        for sample in samples:
            cond = sample.split(".")
            if len(cond) > 1:
                condition = ".".join(cond[:-1])
            else:
                condition = cond[0]
            if sample not in self.sample_dict:
                self.sample_dict[sample] = {"name": sample, "group": condition, "option-text": f"{sample} ({condition})"}

        await self.update_view()


    async def remove_sample(self, samples: List[str]):
        for sample in samples:
            del self.sample_dict[sample]
        sample_list_container = self.query_one("#sample-list-container", VerticalScroll)
        await sample_list_container.remove_children()
        await sample_list_container.mount(OptionList(id="sample-list"))
        sample_list = self.query_one("#sample-list", OptionList)

        if self.sample_dict:
            sample_list.add_options([t["option-text"] for t in self.sample_dict.values()])


    async def select_sample(self, prompt: str):
        group_name_input = self.query_one("#group-name-input", Input)
        for i in self.sample_dict.values():
            if i["option-text"] == prompt:
                group_name_input.value = i["group"]
                self.selected_sample = i["name"]
                break

    async def update_view(self):
        sample_list_container = self.query_one("#sample-list-container", VerticalScroll)
        await sample_list_container.remove_children()
        await sample_list_container.mount(OptionList(id="sample-list"))
        sample_list = self.query_one("#sample-list", OptionList)
        if self.sample_dict:
            sample_list.add_options([t["option-text"] for t in self.sample_dict.values()])






