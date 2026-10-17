import os
import sys
import pymysql

def run_sql_script(cursor, filepath):
    print(f"Executing: {os.path.basename(filepath)} ...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split commands by delimiter or semicolon
    # Handle DELIMITER $$
    if 'DELIMITER $$' in content:
        # Custom parsing for routines
        sections = content.split('DELIMITER $$')
        # First section before DELIMITER $$
        pre = sections[0]
        for stmt in pre.split(';'):
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                cursor.execute(stmt)
        # Remainder
        for sec in sections[1:]:
            parts = sec.split('DELIMITER ;')
            body = parts[0]
            # routine statements are delimited by $$
            for stmt in body.split('$$'):
                stmt = stmt.strip()
                if stmt and not stmt.startswith('--'):
                    cursor.execute(stmt)
            if len(parts) > 1:
                tail = parts[1]
                for stmt in tail.split(';'):
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith('--'):
                        cursor.execute(stmt)
    else:
        # Standard statement splitter
        statements = content.split(';')
        for stmt in statements:
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                cursor.execute(stmt)

def main():
    password = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('MYSQL_ROOT_PASSWORD', 'X@rV#mTk')
    host = os.environ.get('MYSQL_HOST', 'localhost')
    port = int(os.environ.get('MYSQL_PORT', 3306))
    user = os.environ.get('MYSQL_USER', 'root')

    print(f"Connecting to MySQL on {host}:{port} as {user}...")
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            autocommit=True,
            charset='utf8mb4'
        )
    except Exception as e:
        print(f"Error connecting to MySQL: {e}")
        sys.exit(1)

    print("Connected successfully!")
    cursor = conn.cursor()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = [
        os.path.join(base_dir, '01_schema.sql'),
        os.path.join(base_dir, '02_triggers_procedures.sql'),
        os.path.join(base_dir, '03_rbac_provisioning.sql'),
        os.path.join(base_dir, '04_seed_data.sql')
    ]

    for s in scripts:
        if os.path.exists(s):
            run_sql_script(cursor, s)
        else:
            print(f"Warning: Script {s} not found.")

    print("\nDatabase initialization & seeding completed successfully!")
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
