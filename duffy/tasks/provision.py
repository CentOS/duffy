import asyncio
from typing import List, Optional

import aiodns
from celery.utils.log import get_task_logger
from sqlalchemy import func, select

from ..database import sync_session_maker
from ..database.model import Node
from ..database.types import NodeState
from .base import celery
from .locking import Lock
from .mechanisms import MechanismFailure
from .node_pools import ConcreteNodePool, NodePool

log = get_task_logger(__name__)


async def _node_lookup_hostname_from_ipaddr(node: Node):
    """Look up a node hostname from its IP address

    Falls back to the IP address itself on any failure."""
    resolver = aiodns.DNSResolver()
    try:
        lookup_result = await resolver.gethostbyaddr(node.ipaddr)
    except Exception:
        node.hostname = node.ipaddr
    else:
        node.hostname = lookup_result.name or node.ipaddr


@celery.task
def provision_nodes_into_pool(pool_name: str, node_ids: List[id]):
    try:
        pool = NodePool.known_pools[pool_name]
    except KeyError as exc:
        raise RuntimeError(f"[{pool_name}] Unknown pool, bailing out") from exc

    if not node_ids:
        raise RuntimeError(f"[{pool.name}] Empty list of node ids, bailing out")

    log.debug(
        "[%s] Provisioning nodes, id(s): %s", pool.name, ", ".join(str(id) for id in node_ids)
    )

    reuse_nodes = pool.get("reuse-nodes")

    with sync_session_maker() as db_sync_session, db_sync_session.begin():
        # Grab the node objects from the database (again).
        nodes = db_sync_session.execute(select(Node).filter(Node.id.in_(node_ids))).scalars().all()

        if not len(nodes):
            node_ids_str = ", ".join(str(node_id) for node_id in node_ids)
            raise RuntimeError(
                f"[{pool.name}] Didn't find any nodes with these ids: {node_ids_str}"
            )

        if len(nodes) != len(node_ids):
            missing_node_ids = set(node_ids) - {node.id for node in nodes}
            missing_node_ids_str = ", ".join(str(node_id) for node_id in sorted(missing_node_ids))
            log.warning("[%s]: Didn't find nodes with ids: %s", pool.name, missing_node_ids_str)

        log.info("[%s] Attempting to provision %d nodes ...", pool.name, len(nodes))
        try:
            prov_result = pool.provision(nodes)
        except MechanismFailure:
            log.error("[%s] Provisioning failed.", pool.name)
            if not reuse_nodes:
                for node in nodes:
                    db_sync_session.delete(node)
            else:
                for node in nodes:
                    node.state = NodeState.unused
                    node.pool = None
            return
        log.info("[%s] Backend provisioning finished.", pool.name)
        log.debug("[%s] Result: %s", pool.name, prov_result)

        # The playbook needs to provide IP addresses for provisioned nodes as `ipaddr` in the
        # result, otherwise they can't be used.
        log.debug("[%s] Validating backend provisioning node results.", pool.name)
        valid_node_results = {}
        invalid_node_results = []
        for node, node_res in zip(nodes, prov_result["nodes"]):
            if "ipaddr" in node_res:
                valid_node_results[node] = node_res
            else:
                invalid_node_results.append(node_res)

        log.debug("[%s] valid results: %s", pool.name, valid_node_results.values())
        log.debug("[%s] invalid results: %s", pool.name, invalid_node_results)

        if invalid_node_results:
            log.error("[%s] Backend provisioning yielded invalid node results:", pool.name)
            for node_res in invalid_node_results:
                log.error("[%s]     %s", pool.name, node_res)

        # If the playbook provides a hostname, this will be used, otherwise Duffy will attempt a
        # reverse lookup of the IP address and if it fails, fall back to using it as the hostname.

        log.debug("[%s] Setting hostname and ipaddr fields of nodes.", pool.name)
        nodes_need_hostname_looked_up = []
        for node, node_result in valid_node_results.items():
            node.ipaddr = node_result["ipaddr"]
            hostname = node_result.get("hostname")
            if hostname:
                node.hostname = hostname
            else:
                nodes_need_hostname_looked_up.append(node)

        if nodes_need_hostname_looked_up:
            log.debug("[%s] Looking up hostname for nodes from ipaddr...", pool.name)

            asyncio.run(
                asyncio.wait(
                    [
                        _node_lookup_hostname_from_ipaddr(node)
                        for node in nodes_need_hostname_looked_up
                    ]
                )
            )

        log.debug("[%s] Storing information about provisioned hosts.", pool.name)
        for node, node_result in valid_node_results.items():
            node.data["provision"] = node_result
            node.state = NodeState.ready

        leftover_nodes = [node for node in nodes if node not in valid_node_results]
        if leftover_nodes:
            if reuse_nodes:
                log.warning(
                    "[%s] Returning %d left-over reusable node(s)", pool.name, len(leftover_nodes)
                )
                for node in leftover_nodes:
                    node.state = NodeState.unused
                    node.pool = None
                    node.data.pop("provision", None)
            else:
                log.warning(
                    "[%s] Cleaning up %d left-over preallocated node(s)",
                    pool.name,
                    len(leftover_nodes),
                )
                for node in leftover_nodes:
                    db_sync_session.delete(node)


@celery.task
def fill_single_pool(pool_name: str):
    try:
        pool = NodePool.known_pools[pool_name]
    except KeyError as exc:
        raise RuntimeError(f"[{pool_name}] Unknown pool, bailing out") from exc

    log.debug("[%s] Filling up pool ...", pool.name)

    # Determine how many nodes need to be provisioned and commit them to the database so these nodes
    # are considered in future calculations.

    wanted_fill_level = pool["fill-level"]

    # This block uses a lock to prevent concurrently allocating node objects in the database for the
    # same pool. It checks how many 'ready' nodes are allocated to a pool, and how many more are
    # needed to fill it up to spec. If this was done concurrently for the same pool, both tasks
    # would allocate the same number of new nodes, overfilling the pool.
    with Lock(
        key="duffy:fill-single-pool:allocate-nodes-in-db"
    ), sync_session_maker() as db_sync_session, db_sync_session.begin():
        log.debug("[%s] Determining number of available nodes ...", pool.name)
        current_fill_level = db_sync_session.execute(
            select(func.count()).select_from(
                select(Node)
                .filter(
                    Node.active == True,  # noqa: E712
                    Node.pool == pool.name,
                    Node.state.in_((NodeState.ready, NodeState.provisioning)),
                )
                .subquery()
            )
        ).scalar_one()

        quantity = wanted_fill_level - current_fill_level
        log.debug(
            "[%s] ... %d, we want %d, i.e. need %d",
            pool.name,
            current_fill_level,
            wanted_fill_level,
            quantity,
        )

        if quantity <= 0:
            log.debug("[%s] Pool is filled to or above spec.", pool.name)
            return

        reuse_nodes = pool.get("reuse-nodes")
        if reuse_nodes:
            log.debug("[%s] Searching for %d reusable nodes in database", pool.name, quantity)

            usable_nodes_query = select(Node).filter_by(
                active=True, pool=None, reusable=True, state=NodeState.unused
            )
            spec_valid = True
            for key, value in reuse_nodes.items():
                json_item = Node.data[key]
                if isinstance(value, str):
                    cast_item = json_item.as_string()
                    value = pool.render_template(value)
                elif isinstance(value, int):
                    cast_item = json_item.as_integer()
                else:
                    log.error(
                        "[%s] Can't build query for reuse-nodes: %r -> %r", pool.name, key, value
                    )
                    spec_valid = False
                    continue
                usable_nodes_query = usable_nodes_query.filter(cast_item == value)

            if not spec_valid:
                raise RuntimeError(f"[{pool.name}] Skipping filling up")

            # This queries up to `quantity` usable nodes, or fewer.
            usable_nodes_query = usable_nodes_query.limit(quantity)
            log.debug("Usable nodes query: %s", usable_nodes_query)
            nodes = db_sync_session.execute(usable_nodes_query).scalars().all()
            log.info("Found %d suitable unused node(s).", len(nodes))
            if len(nodes) < 1:
                log.warning("[%s] No sense continuing, bailing out.", pool.name)
                return
        else:
            log.debug("[%s] Allocating %d new node objects in database", pool.name, quantity)
            nodes = [Node() for i in range(quantity)]
            db_sync_session.add_all(nodes)

        for node in nodes:
            node.state = NodeState.provisioning
            node.pool = pool.name

    # In (a) follow-up (longer running) transaction(s), provision the nodes. Here, `nodes` is a list
    # of node objects which are in state "provisioning" and assigned to the pool. It can be shorter
    # than `quantity`, e.g. if there aren't enough reusable unused nodes.
    if pool.get("run-parallel", True):
        # Run one sub-task per node in parallel.
        for node in nodes:
            provision_nodes_into_pool.delay(pool.name, [node.id]).forget()
    else:
        # Run one sub-task synchronously for all nodes.
        provision_nodes_into_pool.delay(pool.name, [node.id for node in nodes]).forget()

    log.info("[%s] Filling up nodes: subtasks kicked off", pool.name)


@celery.task
def fill_pools(*, pool_names: Optional[List[str]] = None):
    """Ensure that pools are filled to their configured levels.

    If no pool names are supplied, run for all configured pools.
    """
    log.debug("fill_pools(pool_names=%r) begin", pool_names)

    pools_to_process = list(ConcreteNodePool.iter_pools())

    if not pool_names:
        pool_names = [pool.name for pool in pools_to_process]
    else:
        unknown_pool_names = set(pool_names).difference(pool.name for pool in pools_to_process)
        if unknown_pool_names:
            log.warn("fill_pools: unknown pool names, ignoring: %s", ", ".join(unknown_pool_names))
        pools_to_process = [pool for pool in pools_to_process if pool.name in pool_names]

    for pool in pools_to_process:
        fill_single_pool.delay(pool.name).forget()

    log.debug("fill_pools(%s) end", ", ".join(pool_names))
