from . import BaseTestController


class TestChassis(BaseTestController):

    name = name_plural = "chassis"
    path = "/api/v1/chassis"
    attrs = {"name": "What a Chassis!"}
    unique = "unique"
