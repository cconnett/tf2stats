import sqlite3

class AttributedRow(sqlite3.Row):
    def __getattribute__(self, *args, **kwargs):
        try:
            return sqlite3.Row.__getattribute__(self, *args, **kwargs)
        except AttributeError:
            return sqlite3.Row.__getitem__(self, *args, **kwargs)
