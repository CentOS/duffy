import datetime as dt

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..database import sync_session_maker
from ..database.model import Session, SessionNode
from .base import celery
from .deprovision import deprovision_nodes
from .locking import Lock

log = get_task_logger(__name__)


@celery.task
def expire_sessions():
    with Lock(
        key="duffy:expire_sessions"
    ), sync_session_maker() as db_sync_session, db_sync_session.begin():
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)

        expired_sessions = (
            db_sync_session.execute(
                select(Session)
                .filter(Session.active == True, Session.expires_at < now)  # noqa: E712
                .options(selectinload(Session.session_nodes).selectinload(SessionNode.node))
            )
            .scalars()
            .all()
        )

        for session in expired_sessions:
            log.info("Expiring session (id=%d)", session.id)
            session.active = False
            deprovision_nodes.delay(
                node_ids=[session_node.node_id for session_node in session.session_nodes]
            ).forget()
