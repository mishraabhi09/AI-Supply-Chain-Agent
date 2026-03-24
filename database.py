import sqlite3
from datetime import datetime
from typing import List, Dict, Any

DB_NAME = "supply_chain.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Create Tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Products (
            product_id TEXT PRIMARY KEY,
            name TEXT,
            category TEXT
        );

        CREATE TABLE IF NOT EXISTS Inventory (
            product_id TEXT PRIMARY KEY,
            stock INTEGER,
            reorder_level INTEGER,
            lead_time_days INTEGER,
            FOREIGN KEY(product_id) REFERENCES Products(product_id)
        );

        CREATE TABLE IF NOT EXISTS Suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT,
            location TEXT,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS Orders (
            order_id TEXT PRIMARY KEY,
            product_id TEXT,
            supplier_id TEXT,
            quantity INTEGER,
            cost REAL,
            status TEXT,
            FOREIGN KEY(product_id) REFERENCES Products(product_id),
            FOREIGN KEY(supplier_id) REFERENCES Suppliers(supplier_id)
        );

        CREATE TABLE IF NOT EXISTS Events (
            event_id TEXT PRIMARY KEY,
            type TEXT,
            location TEXT,
            severity TEXT,
            timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS AuditLogs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            action TEXT,
            decision TEXT,
            guardrail_status TEXT,
            details TEXT
        );
    """)

    # Insert Sample Data if empty
    cursor.execute("SELECT COUNT(*) as count FROM Products")
    if cursor.fetchone()['count'] == 0:
        cursor.executescript("""
            INSERT INTO Products (product_id, name, category) VALUES
            ('P001', 'Semiconductor Chips', 'Electronics'),
            ('P002', 'Lithium Batteries', 'Energy'),
            ('P003', 'Steel Frames', 'Materials');

            INSERT INTO Inventory (product_id, stock, reorder_level, lead_time_days) VALUES
            ('P001', 500, 1000, 14),
            ('P002', 1200, 500, 7),
            ('P003', 200, 150, 30);

            INSERT INTO Suppliers (supplier_id, name, location, status) VALUES
            ('S001', 'TechCorp Asia', 'Taiwan', 'Active'),
            ('S002', 'Global Energy', 'Germany', 'Active'),
            ('S003', 'SteelWorks Inc', 'USA', 'Active'),
            ('S004', 'Sanctioned Metals', 'North Korea', 'Restricted'),
            ('S005', 'Backup Chips Ltd', 'Vietnam', 'Active');
        """)

    conn.commit()
    conn.close()

def log_audit(action: str, decision: str, guardrail_status: str, details: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO AuditLogs (timestamp, action, decision, guardrail_status, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), action, decision, guardrail_status, details)
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database {DB_NAME} initialized with sample data.")
