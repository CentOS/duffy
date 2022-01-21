from . import BaseTestController


class TestNode(BaseTestController):

    name = "node"
    path = "/api/v1/nodes"
    attrs = {
        "hostname": "opennebula.nodes.example.com",
        "ipaddr": "192.0.2.1",
        "pool": "virtual-fedora35-x86_64-small",
    }
    unique = True
