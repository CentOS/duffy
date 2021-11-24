from . import BaseTestController


class TestProject(BaseTestController):

    name = "project"
    path = "/api/v1/projects"
    attrs = {
        "name": "Some Honky Project!",
        "ssh_key": "With a honky SSH key!",
    }
    unique = "unique"
