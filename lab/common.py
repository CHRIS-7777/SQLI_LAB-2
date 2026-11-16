"""Shared DB plumbing for every mini-app. (Infrastructure only.)"""
import os
import sqlite3

import pymssql
import pymysql

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

MYSQL_HOST, MYSQL_PORT = "127.0.0.1", 33071
MSSQL_HOST, MSSQL_PORT = "127.0.0.1", 14341

MYSQL_ROOT_PW = "LabRoot#2026"
MSSQL_SA_PW = "Lab#Sqli2026x"
APP_USER, APP_PW = "labapp", "LabApp#2026"

# Databases that provision.py creates (add here if a new app needs one).
MYSQL_DBS = ["staffhub", "rideshare", "vaultdocs"]
MSSQL_DBS = ["ticketdesk", "securebank"]


def sqlite_path(name):
    return os.path.join(DATA_DIR, f"{name}.db")


def sqlite_conn(name):
    """Runtime connection for an app. Python's sqlite3 refuses stacked statements."""
    c = sqlite3.connect(sqlite_path(name), check_same_thread=False, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def mysql_conn(db, admin=False):
    """Runtime = low-privilege labapp (no FILE, only that schema). admin=True for seeding."""
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user="root" if admin else APP_USER,
        password=MYSQL_ROOT_PW if admin else APP_PW,
        database=db, charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=10,
    )


def mssql_conn(db, admin=False):
    """Runtime = low-privilege labapp (db_datareader/db_datawriter). admin=True for seeding."""
    return pymssql.connect(
        server=MSSQL_HOST, port=MSSQL_PORT,
        user="sa" if admin else APP_USER,
        password=MSSQL_SA_PW if admin else APP_PW,
        database=db, autocommit=True, login_timeout=10, as_dict=True,
    )
