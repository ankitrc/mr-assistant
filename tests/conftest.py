"""Shared test fixtures: a connection as the application role (mr_app)."""

import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@pytest.fixture
def app_db():
    """Connection as mr_app. Use as_employee(id) to act as a given user inside the transaction."""
    e = os.environ
    conn = psycopg.connect(host=e["POSTGRES_HOST"], port=e["POSTGRES_PORT"], dbname=e["POSTGRES_DB"],
                           user=e["POSTGRES_APP_USER"], password=e["POSTGRES_APP_PASSWORD"])
    yield conn
    conn.rollback()
    conn.close()


def as_employee(conn, employee_id):
    """Set the current user for this transaction only (is_local = true)."""
    conn.execute("SELECT set_config('app.employee_id', %s, true)", (str(employee_id),))


def scalar(conn, query, *args):
    return conn.execute(query, args).fetchone()[0]


@pytest.fixture(scope="session", autouse=True)
def _close_pool():
    yield
    from mr_assistant.db import close_pool
    close_pool()
