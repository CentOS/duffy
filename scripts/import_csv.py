#!/usr/bin/env python3

import csv
import sys
from pathlib import Path

import click
import xdg.BaseDirectory
import yaml
from sqlalchemy import select

from duffy.configuration import read_configuration
from duffy.database import init_sync_model, sync_session_maker
from duffy.database.model import Tenant

DEFAULT_CONFIG_LOCATIONS = ("/etc/duffy", f"{xdg.BaseDirectory.xdg_config_home}/duffy")
DEFAULT_CONFIG_PATHS = tuple(Path(loc) for loc in DEFAULT_CONFIG_LOCATIONS)


class dump_dialect(csv.unix_dialect):
    quotechar = "'"


@click.group()
@click.option(
    "config_paths",
    "--config",
    "-c",
    type=click.Path(exists=True),
    multiple=True,
    help=(
        "Read configuration from the specified YAML files or directories instead of the default"
        f" paths ({', '.join(DEFAULT_CONFIG_LOCATIONS)})"
    ),
    metavar="FILE_OR_DIR",
)
def cli(config_paths):
    if not config_paths:
        # Ignore non-existent default paths
        config_paths = tuple(path for path in DEFAULT_CONFIG_PATHS if path.exists())

    read_configuration(*config_paths, clear=True, validate=True)


def read_csv_files(users_file, userkeys_file):
    users = {}
    api_keys_to_users = {}

    with open(users_file) as fp:
        users_csv = csv.reader(fp, dialect=dump_dialect)
        for api_key, project, tenant_name, created_at, limit in users_csv:
            users[tenant_name] = {"api_key": api_key}
            assert api_key not in api_keys_to_users
            api_keys_to_users[api_key] = tenant_name

    with open(userkeys_file) as fp:
        userkeys_csv = csv.reader(fp, dialect=dump_dialect)
        for id_, api_key, ssh_key in userkeys_csv:
            ssh_key = ssh_key.strip()
            tenant_dict = users[api_keys_to_users[api_key]]
            if "ssh_key" in tenant_dict:
                tenant_dict["ssh_key"] += f"\n{ssh_key}"
            else:
                tenant_dict["ssh_key"] = ssh_key

    skip_tenants_names = set()

    for tenant_name, tenant_dict in users.items():
        if tenant_dict["api_key"].endswith("DISABLED"):
            print(f"Skipping {tenant_name}: disabled", file=sys.stderr)
            skip_tenants_names.add(tenant_name)

        if not tenant_dict.get("ssh_key"):
            print(f"Skipping {tenant_name}: no SSH key", file=sys.stderr)
            skip_tenants_names.add(tenant_name)

    for tenant_name in skip_tenants_names:
        tenant_dict = users[tenant_name]
        api_keys_to_users.pop(tenant_dict["api_key"])
        del users[tenant_name]

    return users, api_keys_to_users


@cli.command()
@click.option("--commit/--dry-run")
@click.argument("users_file", required=False)
@click.argument("userkeys_file", required=False)
def import_db(commit, users_file, userkeys_file):
    """Import tenants from CSV files into DB."""
    users, api_keys_to_users = read_csv_files(users_file, userkeys_file)

    init_sync_model()

    with sync_session_maker() as session:
        for tenant_name, tenant_dict in users.items():
            tenant = session.execute(
                select(Tenant).filter_by(name=tenant_name)
            ).scalar_one_or_none()

            if tenant:
                print(f"Skipping {tenant_name}: exists", file=sys.stderr)
                continue

            tenant = Tenant(name=tenant_name, **tenant_dict)
            session.add(tenant)

        if commit:
            print("Committing tenants to database")
            session.commit()
        else:
            print("Dry-run: rolling back transaction")
            session.rollback()


@cli.command
@click.argument("users_file", required=False)
@click.argument("userkeys_file", required=False)
def generate_usermap(users_file, userkeys_file):
    """Generate a usermap for the metaclient from CSV files."""
    users, api_keys_to_users = read_csv_files(users_file, userkeys_file)
    config_dict = {"metaclient": {"usermap": api_keys_to_users}}

    yaml.dump(config_dict, sys.stdout)


if __name__ == "__main__":
    cli()
