from __future__ import annotations

from pathlib import Path

from app.core.database_url import resolve_database_url_driver


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_mysql_pymysql_url_prefers_mysqldb_when_mysqlclient_available() -> None:
    resolved = resolve_database_url_driver(
        "mysql+pymysql://user:pass@mysql:3306/t_quant?charset=utf8mb4",
        mysqlclient_available=lambda: True,
        pymysql_available=lambda: True,
    )

    assert resolved == "mysql+mysqldb://user:pass@mysql:3306/t_quant?charset=utf8mb4"


def test_mysql_mysqldb_url_falls_back_to_pymysql_when_mysqlclient_missing() -> None:
    resolved = resolve_database_url_driver(
        "mysql+mysqldb://user:pass@mysql:3306/t_quant?charset=utf8mb4",
        mysqlclient_available=lambda: False,
        pymysql_available=lambda: True,
    )

    assert resolved == "mysql+pymysql://user:pass@mysql:3306/t_quant?charset=utf8mb4"


def test_sqlite_url_is_not_rewritten() -> None:
    resolved = resolve_database_url_driver(
        "sqlite:///./data/t_quant.db",
        mysqlclient_available=lambda: True,
        pymysql_available=lambda: True,
    )

    assert resolved == "sqlite:///./data/t_quant.db"


def test_mysql_deployment_templates_default_to_mysqldb() -> None:
    compose = (ROOT_DIR / "docker-compose.mysql.yml").read_text(encoding="utf-8")
    env_example = (ROOT_DIR / ".env.docker.example").read_text(encoding="utf-8")
    deploy_script = (ROOT_DIR / "scripts" / "deploy_cloud_server.sh").read_text(encoding="utf-8")

    assert "DATABASE_URL: mysql+mysqldb://" in compose
    assert "DATABASE_URL=mysql+mysqldb://" in env_example
    assert "mysql+mysqldb://" in deploy_script
    assert "DATABASE_URL: mysql+pymysql://" not in compose
