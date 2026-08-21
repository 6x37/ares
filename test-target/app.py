"""Intentionally vulnerable demo app (authorized local test target for Arès)."""
import sqlite3
import os
from flask import Flask, request

app = Flask(__name__)


@app.route("/login")
def login():
    user = request.args.get("user", "")
    # VULN: SQL injection — user input concatenated straight into the query.
    conn = sqlite3.connect(":memory:")
    q = "SELECT * FROM users WHERE name = '" + user + "'"
    return str(conn.execute(q).fetchall())


@app.route("/ping")
def ping():
    host = request.args.get("host", "127.0.0.1")
    # VULN: command injection — unsanitized input into os.system.
    return str(os.system("ping -c 1 " + host))


@app.route("/read")
def read_file():
    name = request.args.get("f", "readme.txt")
    # VULN: path traversal — no sanitization of the path.
    with open("/app/data/" + name) as fh:
        return fh.read()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
