"""Accesso SQLite e inizializzazione dello schema."""

import os
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parola TEXT NOT NULL,
    frase_indizio TEXT NOT NULL,
    nome TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


def initialize_database(database_path):
    database_directory = os.path.dirname(database_path)
    if database_directory:
        os.makedirs(database_directory, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute(SCHEMA)


def connect_to_database(database_path):
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection
