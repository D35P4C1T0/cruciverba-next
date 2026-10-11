"""Accesso SQLite e inizializzazione dello schema."""

import os
import sqlite3
from contextlib import closing

from flask import current_app


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

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(SCHEMA)
        connection.commit()


def connect_to_database(database_path):
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_db():
    initialize_database(current_app.config["DATABASE_PATH"])


def get_db_connection():
    return connect_to_database(current_app.config["DATABASE_PATH"])


def add_submission(word, clue, name):
    with closing(get_db_connection()) as connection:
        connection.execute(
            "INSERT INTO submissions (parola, frase_indizio, nome) VALUES (?, ?, ?)",
            (word, clue, name),
        )
        connection.commit()


def list_submissions():
    with closing(get_db_connection()) as connection:
        return connection.execute(
            "SELECT * FROM submissions ORDER BY timestamp DESC"
        ).fetchall()


def remove_submission(submission_id):
    """Delete a contribution; return whether it existed."""
    with closing(get_db_connection()) as connection:
        cursor = connection.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
        connection.commit()
        return cursor.rowcount > 0
