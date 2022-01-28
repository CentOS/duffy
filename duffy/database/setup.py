import sys
import uuid
from pathlib import Path

import alembic.command
import alembic.config
from sqlalchemy import inspect

from ..configuration import config

# Import the DB model here so its classes are considered by metadata.create_all() below.
from . import get_sync_engine, metadata, model, sync_session_maker  # noqa: F401

HERE = Path(__file__).parent


def setup_db_schema():
    engine = get_sync_engine()

    inspection_result = inspect(engine)

    present_tables = sorted(n for n in metadata.tables if inspection_result.has_table(n))

    if present_tables:
        print(f"Tables already present: {', '.join(present_tables)}", file=sys.stderr)
        print("Refusing to change database schema.", file=sys.stderr)
        sys.exit(1)

    with engine.begin():
        print("Creating database schema")
        metadata.create_all(bind=engine)

        print("Setting up database migrations")
        cfg = alembic.config.Config()
        cfg.set_main_option("script_location", str(HERE / "migrations"))
        cfg.set_main_option("sqlalchemy.url", config["database"]["sqlalchemy"]["sync_url"])

        alembic.command.stamp(cfg, "head")


def _gen_test_api_key(tenant_name):
    """Generate deterministic API keys for test users."""
    return uuid.uuid5(uuid.NAMESPACE_OID, tenant_name)


def _gen_test_data_objs():
    objs = set()

    admin = model.Tenant(
        name="admin", api_key=_gen_test_api_key("admin"), ssh_key="Boo", is_admin=True
    )
    objs.add(admin)

    tenant = model.Tenant(name="tenant", api_key=_gen_test_api_key("tenant"), ssh_key="Boo!")
    objs.add(tenant)

    node_specs = [
        {
            "hostname": "node-seamicro-1.example.net",
            "ipaddr": "192.168.0.11",
            "pool": "physical-centos8stream-x86_64",
            "data": {"architecture": "x86_64"},
        },
        {
            "hostname": "node-seamicro-2.example.net",
            "ipaddr": "192.168.0.12",
            "pool": "physical-fedora35-x86_64",
            "data": {"architecture": "x86_64"},
        },
        {
            "hostname": "node-seamicro-3.example.net",
            "ipaddr": "192.168.0.13",
            "data": {"architecture": "x86_64"},
        },
        {
            "hostname": "node-seamicro-4.example.net",
            "ipaddr": "192.168.0.14",
            "data": {"architecture": "x86_64"},
        },
    ]

    for quantity, flavour, ipaddrbase in (
        (40, "small", "192.168.1.10"),
        (20, "medium", "192.168.2.10"),
        (10, "large", "192.168.3.10"),
    ):
        ipprefix, lastoctetbase = ipaddrbase.rsplit(".", 1)
        lastoctetbase = int(lastoctetbase)
        for index in range(1, quantity + 1):
            lastoctet = lastoctetbase + index
            if index % 2:
                distro = "fedora35"
            else:
                distro = "centos8stream"
            node_specs.append(
                {
                    "hostname": f"node-opennebula-{flavour}-{index}.example.net",
                    "ipaddr": f"{ipprefix}.{lastoctet}",
                    "pool": f"virtual-{distro}-x86_64-{flavour}",
                }
            )

    for node_spec in node_specs:
        if node_spec.get("pool"):
            state = "ready"
        else:
            state = "unused"
        node = model.Node(state=state, **node_spec)
        objs.add(node)

    return objs


def setup_db_test_data():
    db_sync_session = sync_session_maker()
    print("Creating test data")
    with db_sync_session.begin():
        for obj in _gen_test_data_objs():
            db_sync_session.add(obj)

    print("Caution! Created tenants with deterministic API keys:")
    print(f"\tadmin:{_gen_test_api_key('admin')}")
    print(f"\ttenant:{_gen_test_api_key('tenant')}")
    print("Don't use in production!")
