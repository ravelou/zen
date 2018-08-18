
"""Module with needed functions for the views.py

"""
import os
import io
import sqlite3
import flask
from zen.cmn import loadConfig, loadJson

from app import appweb

def connect():
    if not hasattr(flask.g, "database"):
        setattr(flask.g, "database", sqlite3.connect(
            os.path.join(appweb.root_path, "..", "pay.db")))
        flask.g.database.row_factory = sqlite3.Row
    return flask.g.database.cursor()


def search(table="transaction", **kw):
    cursor = connect()
    cursor.execute(
        "SELECT * FROM %s WHERE %s=? ORDER BY timestamp DESC;" % (
            table, kw.keys()[0]),
        (kw.values()[0], )
    )
    result = cursor.fetchall()
    return [dict(zip(row.keys(), row)) for row in result]


def getFilesFromDirectory(dirname, ext, method=None):
    files_data = {}
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    #base = os.path.dirname(__file__)
    if bool(dirname):
        for root, dirs, files in os.walk(os.path.join(base,'zen', dirname)):
            for filename in files:
                if filename.endswith(ext):
                    if method == 'json':
                        files_data[filename.replace(ext, "")] = loadJson(
                            os.path.join(root, filename))
                    else:
                        with io.open(os.path.join(root, filename), 'r') as in_:
                            files_data[filename.replace(ext, "")] = in_.read()
    return files_data
