import sqlite3
def run():
    conn = sqlite3.connect("supply_chain.db")
    c = conn.cursor()
    try:
        c.executescript('''
            INSERT OR IGNORE INTO Products (product_id, name, category) VALUES ('SKU-1001', 'High-Tensile Bolts', 'Hardware');
            INSERT OR IGNORE INTO Inventory (product_id, stock, reorder_level, lead_time_days) VALUES ('SKU-1001', 50, 500, 14);
            INSERT OR IGNORE INTO Suppliers (supplier_id, name, location, status) VALUES ('S006', 'FastenerCo', 'Rotterdam', 'Active');
        ''')
        conn.commit()
        print("Inserted mock data!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
