from importlib.metadata import (PackageNotFoundError,  # pragma: no cover
                                version)

from migration.log.setting import set_log

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

set_log()
