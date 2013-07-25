CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kindle_name TEXT UNIQUE NOT NULL,
  access_token BLOB,
  emailer TEXT,
  active TINYINT NOT NULL,
  delta_cursor TEXT
);

CREATE TABLE IF NOT EXISTS books (
    id INTEGER,
    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_contents INTEGER,
    pathname TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS booksbyuser (
	id INTEGER PRIMARY KEY,
	book_id INTEGER
);