DROP TABLE IF EXISTS history;

CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    leaderId INTEGER,
    sender TEXT NOT NULL,
    content TEXT NOT NULL
);

DROP TABLE IF EXISTS settings;

CREATE TABLE settings (
    leaderId INTEGER PRIMARY KEY,
    settings TEXT NOT NULL
);