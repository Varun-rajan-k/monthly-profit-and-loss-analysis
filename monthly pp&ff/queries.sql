-- Named queries used by analysis.py (each block starts with "-- name: <query_name>")

-- name: categories
SELECT kind, name FROM categories ORDER BY kind, rowid;

-- name: monthly_profit_loss
SELECT month, income, expenses, profit_loss
FROM monthly_profit_loss
ORDER BY month;

-- name: running_total
SELECT month, SUM(profit_loss) OVER (ORDER BY month) AS running_total
FROM monthly_profit_loss
ORDER BY month;

-- name: expense_by_category
SELECT category, SUM(amount) AS total
FROM transactions
WHERE kind = 'expense'
GROUP BY category
ORDER BY total DESC;

-- name: income_by_category
SELECT category, SUM(amount) AS total
FROM transactions
WHERE kind = 'income'
GROUP BY category
ORDER BY total DESC;
