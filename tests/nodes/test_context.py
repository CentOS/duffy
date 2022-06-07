from asyncio.subprocess import DEVNULL, PIPE
from unittest import mock

import pytest

from duffy.nodes import context


@pytest.mark.parametrize("with_stdin", (True, False))
@pytest.mark.parametrize("success", (True, False))
@mock.patch("asyncio.create_subprocess_exec")
async def test_run_remote_cmd(create_subprocess_exec, success, with_stdin):
    create_subprocess_exec.return_value = proc = mock.AsyncMock()
    proc.returncode = not success
    proc.communicate.return_value = (None, None)

    CMD = "what a command"
    NODE = "node.domain.tld"
    if with_stdin:
        STDIN_TEXT = "BOOO"
    else:
        STDIN_TEXT = None
    result = await context.run_remote_cmd(node=NODE, cmd=CMD, stdin_text=STDIN_TEXT)

    create_subprocess_exec.assert_awaited_with(
        *(context.SSH_CMD_FLAGS + [f"root@{NODE}", CMD]),
        stdin=PIPE,
        stdout=DEVNULL,
        stderr=DEVNULL,
    )

    proc.communicate.assert_awaited()
    input_value = proc.communicate.call_args.kwargs["input"]
    if with_stdin:
        assert STDIN_TEXT.encode() == input_value
    else:
        assert input_value is None

    proc.wait.assert_awaited_once_with()

    if success:
        assert result == NODE
    else:
        assert result is None


@mock.patch("duffy.nodes.context.run_remote_cmd")
async def test_decontextualize_one(run_remote_cmd):
    run_remote_cmd.return_value = sentinel = object()
    NODE = "node.domain.tld"

    result = await context.decontextualize_one(node=NODE)

    run_remote_cmd.assert_awaited_once_with(NODE, context.SSH_REMOTE_DECONTEXTUALIZE_CMD)

    assert result == sentinel


@mock.patch("duffy.nodes.context.decontextualize_one")
async def test_decontextualize(decontextualize_one):
    nodes = [f"node{idx}.domain.tld" for idx in range(1, 6)]
    decontextualize_one.side_effect = nodes

    decontextualize_result = await context.decontextualize(nodes)

    assert decontextualize_result == nodes

    decontextualize_one.assert_has_awaits(mock.call(node=node) for node in nodes)


@pytest.mark.parametrize("decontextualize_fail", (False, True))
@mock.patch("duffy.nodes.context.run_remote_cmd")
@mock.patch("duffy.nodes.context.decontextualize_one")
async def test_contextualize_one(decontextualize_one, run_remote_cmd, decontextualize_fail):
    SSH_PUBKEY = "BOOP"
    NODE = "node.domain.tld"

    if decontextualize_fail:
        decontextualize_one.return_value = False
    else:
        run_remote_cmd.return_value = NODE

    result = await context.contextualize_one(ssh_pubkey=SSH_PUBKEY, node=NODE)

    decontextualize_one.assert_awaited_once_with(NODE)

    if not decontextualize_fail:
        run_remote_cmd.assert_awaited_once()
        assert run_remote_cmd.call_args.args == (NODE, context.SSH_REMOTE_CONTEXTUALIZE_CMD)
        assert run_remote_cmd.call_args.kwargs == {
            "stdin_text": f"{context.TENANT_CRED_SEPARATOR}\n{SSH_PUBKEY}\n"
        }
        assert result == NODE
    else:
        run_remote_cmd.assert_not_awaited()
        assert result is None


@mock.patch("duffy.nodes.context.contextualize_one")
async def test_contextualize(contextualize_one):
    nodes = [f"node{idx}.domain.tld" for idx in range(1, 6)]
    contextualize_one.side_effect = nodes

    SSH_PUBKEY = "BOOP"

    contextualize_result = await context.contextualize(nodes, SSH_PUBKEY)

    assert contextualize_result == nodes

    contextualize_one.assert_has_awaits(
        mock.call(ssh_pubkey=SSH_PUBKEY, node=node) for node in nodes
    )
