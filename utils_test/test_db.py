import sqlite3 # To work with SQLite database.

"""
Opens a connection to the 'monitor.db' database. 'with' context manager is used,
which automatically closes the connection after the end of the block.
"""
with sqlite3.connect("../monitor.db") as conn:
    # A cursor object is created for executing SQL commands in the database.
    cursor = conn.cursor()

    #It executes an SQL query that retrieves all rows from the 'ping_status' table.
    for row in cursor.execute("SELECT * FROM ping_status"):
        print(row)