from . import BaseTestController


class TestTenant(BaseTestController):

    name = "tenant"
    path = "/api/v1/tenants"
    attrs = {
        "name": "Some Honky Tenant!",
        "is_admin": False,
        "ssh_key": "With a honky SSH key!",
    }
    unique = "unique"
