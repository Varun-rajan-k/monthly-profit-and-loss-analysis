-- Monthly Profit and Loss Analysis: database schema (SQLite)
-- Run by analysis.py, or manually:  sqlite3 pnl.db < schema.sql

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS monthly_profit_loss;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS categories;

-- The options you can choose from in each section.
CREATE TABLE categories (
    kind  TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    name  TEXT NOT NULL,
    PRIMARY KEY (kind, name)
);

INSERT INTO categories (kind, name) VALUES
    ('income',  'Salary'),
    ('income',  'Business'),
    ('income',  'Other income'),
    ('expense', 'Rent'),
    ('expense', 'Shopping'),
    ('expense', 'Snacks'),
    ('expense', 'Clothes');

-- One row per money-in or money-out entry.
CREATE TABLE transactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_date   TEXT NOT NULL,                                      -- YYYY-MM-DD
    kind       TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    category   TEXT NOT NULL,
    amount     REAL NOT NULL CHECK (amount >= 0),
    FOREIGN KEY (kind, category) REFERENCES categories (kind, name)
);

CREATE INDEX idx_transactions_date ON transactions (txn_date);

-- Consolidates raw transactions into one row per month.
CREATE VIEW monthly_profit_loss AS
SELECT
    strftime('%Y-%m', txn_date)                                   AS month,
    SUM(CASE WHEN kind = 'income'  THEN amount ELSE 0 END)        AS income,
    SUM(CASE WHEN kind = 'expense' THEN amount ELSE 0 END)        AS expenses,
    SUM(CASE WHEN kind = 'income'  THEN amount ELSE -amount END)  AS profit_loss
FROM transactions
GROUP BY strftime('%Y-%m', txn_date);
