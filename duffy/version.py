try:
    from importlib import metadata
except ImportError:  # pragma: no cover
    import importlib_metadata as metadata


__version__ = metadata.version("duffy")
