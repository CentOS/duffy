from typing import List, Optional

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
        key=f"duffy:fill-single-pool:{pool_name}",
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
            log.info("Found %d suitable unused nodes.", len(nodes))
        else:
            log.debug("[%s] Allocating %d new node objects in database", pool.name, quantity)
            nodes = [Node() for i in range(quantity)]
            db_sync_session.add_all(nodes)

        for node in nodes:
            node.state = NodeState.provisioning
            node.pool = pool.name

    # In a second (longer running) transaction, provision the nodes.

    with sync_session_maker() as db_sync_session, db_sync_session.begin():
        # Make the nodes available in the new transaction/session.
        nodes = [db_sync_session.merge(node, load=False) for node in nodes]

        # Here, `nodes` is a list of node objects which are in state "provisioning" and assigned
        # to the pool. It can be shorter than `quantity`, e.g. if there aren't enough reusable
        # unused nodes.
        log.info("[%s] Attempting to provision %d nodes ...", pool.name, quantity)
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

        if reuse_nodes:
            # As existing nodes are used, hostname and ipaddr (if any) in the results will be
            # ignored, only the size of the result set will be considered.
            valid_node_results = prov_result["nodes"]
        else:
            # The playbook needs to provide hostname and ipaddr for provisioned nodes in the
            # result, otherwise they can't be used.
            log.debug("[%s] Validating backend provisioning node results.", pool.name)
            valid_node_results = []
            invalid_node_results = []
            for node_res in prov_result["nodes"]:
                hostname = node_res.get("hostname")
                ipaddr = node_res.get("ipaddr")

                if not (hostname and ipaddr):
                    invalid_node_results.append(node_res)
                    continue

                valid_node_results.append(node_res)

            log.debug("[%s] valid results: %s", pool.name, valid_node_results)
            log.debug("[%s] invalid results: %s", pool.name, invalid_node_results)

            if invalid_node_results:
                log.error("[%s] Backend provisioning yielded invalid node results:", pool.name)
                for node_res in invalid_node_results:
                    log.error("[%s]     %s", pool.name, node_res)

            log.debug("[%s] Setting hostname and ipaddr fields of nodes.", pool.name)
            for node, node_result in zip(nodes, valid_node_results):
                node.hostname = node_result["hostname"]
                node.ipaddr = node_result["ipaddr"]

        log.debug("[%s] Storing information about provisioned hosts.", pool.name)
        for node, node_result in zip(nodes, valid_node_results):
            if not reuse_nodes:
                node.hostname = node_result["hostname"]
                node.ipaddr = node_result["ipaddr"]
            node.data["provision"] = node_result
            node.state = NodeState.ready

        num_valid_nodes = len(valid_node_results)
        leftover_nodes = nodes[num_valid_nodes:]
        if leftover_nodes:
            if reuse_nodes:
                log.warning(
                    "[%s] Returning %d left-over reusable nodes", pool.name, len(leftover_nodes)
                )
                for node in leftover_nodes:
                    node.state = NodeState.unused
                    node.pool = None
                    node.data.pop("provision", None)
            else:
                log.warning(
                    "[%s] Cleaning up %d left-over preallocated nodes",
                    pool.name,
                    len(leftover_nodes),
                )
                for node in leftover_nodes:
                    db_sync_session.delete(node)

    log.info("[%s] Filling up nodes finished", pool.name)


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
