from abc import ABC, abstractmethod


class LogFormat(ABC):
    def __init__(self, changes):
        self.changes = changes
        self.output = ""

    @abstractmethod
    def print_history(self, history):
        pass

    @abstractmethod
    def print_added_item(self, source, rev):
        pass

    def print_modified_item(self, source, data):
        if "history" in data:
            self.print_history(data["history"])

    @abstractmethod
    def print_deleted_item(self, source, rev):
        pass

    def print_added(self, changes):
        for source, data in changes.items():
            self.print_added_item(source, data)

    def print_modified(self, changes):
        for source, data in changes.items():
            self.print_modified_item(source, data)

    def print_deleted(self, changes):
        for source, data in changes.items():
            self.print_deleted_item(source, data)

    def generate(self):
        if self.changes["added"]:
            self.print_added(self.changes["added"])

        if self.changes["modified"]:
            self.print_modified(self.changes["modified"])

        if self.changes["deleted"]:
            self.print_deleted(self.changes["deleted"])

    def add_line(self, line=""):
        if self.output:
            self.output += "\n"
        self.output += line

    def display(self):
        print(self.output)


class LogTextFormat(LogFormat):
    def print_history(self, history):
        for line in history:
            self.add_line("  {}".format(line))

    def print_added_item(self, source, rev):
        self.add_line("A {}: {}".format(source, rev))

    def print_modified_item(self, source, data):
        self.add_line("M {}: {} .. {}".format(source, data["from"], data["to"]))
        super().print_modified_item(source, data)

    def print_deleted_item(self, source, rev):
        self.add_line("D {}: {}".format(source, rev))


class LogMarkdownFormat(LogFormat):
    def print_history(self, history):
        for line in history:
            self.add_line("  - {}".format(line))

    def print_added_item(self, source, rev):
        self.add_line("- {} at revision {}".format(source, rev))

    def print_modified_item(self, source, data):
        self.add_line(
            "- {} changed from {} to {}".format(source, data["from"], data["to"])
        )
        super().print_modified_item(source, data)

    def print_deleted_item(self, source, rev):
        self.add_line("- {} at revision {}".format(source, rev))

    def print_added(self, changes):
        self.add_line("## Added projects")
        super().print_added(changes)
        self.add_line()

    def print_modified(self, changes):
        self.add_line("## Modified projects")
        super().print_modified(changes)
        self.add_line()

    def print_deleted(self, changes):
        self.add_line("## Deleted projects")
        super().print_deleted(changes)
        self.add_line()
