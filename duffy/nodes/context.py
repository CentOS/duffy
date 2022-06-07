"""
Contextualize nodes.

This means appending the SSH public key of a tenant to
/root/.ssh/authorized_keys on the node.

The file must already be present and contain the SSH public key of the Duffy
user.
"""

import asyncio
import logging
from asyncio.subprocess import DEVNULL, PIPE
from typing import List, Optional, Sequence

log = logging.getLogger(__name__)

SSH_CMD_FLAGS_BASE = ["/usr/bin/ssh", "-q"]
SSH_CMD_OPTIONS = [
    "CheckHostIP=no",
    "ConnectionAttempts=5",
    "EscapeChar=none",
    "ForwardAgent=no",
    "ForwardX11=no",
    "PasswordAuthentication=no",
    "PubkeyAuthentication=yes",
    "RequestTTY=no",
    "StrictHostKeyChecking=no",
    "UserKnownHostsFile=/dev/null",
]
SSH_CMD_FLAGS = SSH_CMD_FLAGS_BASE + [item for option in SSH_CMD_OPTIONS for item in ("-o", option)]
TENANT_CRED_SEPARATOR = "### DUFFY tenant credentials"
SSH_REMOTE_CONTEXTUALIZE_CMD = "cat - >> ~root/.ssh/authorized_keys"
SSH_REMOTE_DECONTEXTUALIZE_CMD = (
    f"sed -i -n '/{TENANT_CRED_SEPARATOR}/q;p' ~root/.ssh/authorized_keys"
)


async def run_remote_cmd(node: str, cmd: str, stdin_text: Optional[str] = None) -> Optional[str]:
    """Run a shell command on a remote node."""
    log.debug("run_remote_cmd(%r, %r, ...)", node, cmd)
    ssh_flags_cmd = SSH_CMD_FLAGS + [f"root@{node}", cmd]

    proc = await asyncio.create_subprocess_exec(
        *ssh_flags_cmd, stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL
    )

    if stdin_text:
        inputval = stdin_text.encode()
    else:
        inputval = None
    stdout, stderr = await proc.communicate(input=inputval)

    await proc.wait()

    if not proc.returncode:
        return node


async def decontextualize_one(node: str) -> Optional[str]:
    """Decontextualize one node.

    Removes a previously added tenant SSH public key from the list of
    authorized keys on a node (if it exists).
    """
    return await run_remote_cmd(node, SSH_REMOTE_DECONTEXTUALIZE_CMD)


async def decontextualize(nodes: Sequence[str]) -> List[Optional[str]]:
    """Decontextualize several nodes."""
    return await asyncio.gather(*(decontextualize_one(node=node) for node in nodes))


async def contextualize_one(node: str, ssh_pubkey: str) -> Optional[str]:
    """Contextualize one node.

    This adds the provided SSH public key to the list of authorized keys on
    the provisioned node and returns the name/IP address of the node on
    success.
    """
    if await decontextualize_one(node):
        stdin_text = f"{TENANT_CRED_SEPARATOR}\n{ssh_pubkey}\n"
        return await run_remote_cmd(node, SSH_REMOTE_CONTEXTUALIZE_CMD, stdin_text=stdin_text)


async def contextualize(nodes: Sequence[str], ssh_pubkey: str) -> List[Optional[str]]:
    """Contextualize several nodes."""
    return await asyncio.gather(
        *(contextualize_one(node=node, ssh_pubkey=ssh_pubkey) for node in nodes)
    )
