from __future__ import annotations

from collections.abc import Callable
from importlib.util import find_spec

from sqlalchemy.engine import make_url


def _module_available(module_name: str) -> bool:
    return find_spec(module_name) is not None


def resolve_database_url_driver(
    database_url: str,
    *,
    mysqlclient_available: Callable[[], bool] | None = None,
    pymysql_available: Callable[[], bool] | None = None,
) -> str:
    """Prefer mysqlclient for MySQL while keeping PyMySQL as a deployment fallback."""

    if not database_url.startswith("mysql"):
        return database_url

    mysqlclient_available = mysqlclient_available or (lambda: _module_available("MySQLdb"))
    pymysql_available = pymysql_available or (lambda: _module_available("pymysql"))

    url = make_url(database_url)
    driver = url.drivername.lower()
    if mysqlclient_available() and driver in {"mysql", "mysql+pymysql"}:
        return url.set(drivername="mysql+mysqldb").render_as_string(hide_password=False)
    if driver == "mysql+mysqldb" and not mysqlclient_available() and pymysql_available():
        return url.set(drivername="mysql+pymysql").render_as_string(hide_password=False)
    return database_url
