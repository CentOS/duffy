try:
    from asyncio import current_task
except ImportError:  # pragma: no cover
    # Python < 3.7
    current_task = None

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker


# use custom metadata to specify naming convention
def constraint_column_names(constraint, table):
    return "_".join(c.name for c in constraint.columns)


def constraint_column_labels(constraint, table):  # pragma: no cover
    return "_".join(c._label for c in constraint.columns)


naming_convention = {
    "column_names": constraint_column_names,
    "column_labels": constraint_column_labels,
    "ix": "%(column_labels)s_index",
    "uq": "%(table_name)s_%(column_names)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_names)s_%(referred_table_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=naming_convention)

Base = declarative_base(metadata=metadata)

# Global session managers: DBSession() and AsyncDBSession() return the thread-local session object
# appropriate for the current web request.
maker = sessionmaker(future=True)
DBSession = scoped_session(maker)

if current_task:  # pragma: no cover
    async_maker = sessionmaker(class_=AsyncSession, future=True)
    AsyncDBSession = async_scoped_session(async_maker, scopefunc=current_task)
else:
    # Python < 3.7
    AsyncDBSession = None  # pragma: no cover


def init_model(engine, async_engine=None):
    DBSession.remove()
    DBSession.configure(bind=engine)

    if async_engine:  # pragma: no cover
        if AsyncDBSession:
            AsyncDBSession.remove()
            AsyncDBSession.configure(bind=async_engine)
        else:
            # Python < 3.7
            raise RuntimeError("Async DB sessions need Python >= 3.7")
