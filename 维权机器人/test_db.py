"""
FBI IC3 Bot - Database Diagnostic Tool
Run in PowerShell: python test_db.py
"""
import asyncio
import os

def load_env(path=".env"):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        print("OK  .env loaded")
    except FileNotFoundError:
        print("WARN  .env not found, using system environment variables")

load_env()

async def main():
    try:
        import asyncpg
    except ImportError:
        print("ERR  asyncpg not installed.")
        print("     Run:  pip install asyncpg")
        return

    host     = os.getenv("DB_HOST",     "localhost")
    port     = int(os.getenv("DB_PORT", "5432"))
    database = os.getenv("DB_NAME",     "ic3_bot")
    user     = os.getenv("DB_USER",     "postgres")
    password = os.getenv("DB_PASSWORD", "")

    print("")
    print("=" * 55)
    print("  IC3 DATABASE DIAGNOSTIC")
    print("=" * 55)
    print(f"  Host     : {host}:{port}")
    print(f"  Database : {database}")
    print(f"  User     : {user}")
    print(f"  Password : {'SET' if password else 'EMPTY (possible issue!)'}")
    print("=" * 55)

    # ── Step 1: Connect ────────────────────────────────────
    try:
        conn = await asyncpg.connect(
            host=host, port=port, database=database,
            user=user, password=password,
            timeout=10
        )
        print("\n[1] CONNECTION ........... OK")
    except Exception as e:
        print(f"\n[1] CONNECTION ........... FAILED")
        print(f"    Error: {e}")
        print("")
        print("  Possible causes:")
        print("  - PostgreSQL service not running")
        print("    Fix: Start PostgreSQL in Services / pgAdmin")
        print("  - Wrong DB_NAME in .env")
        print("    Fix: Check pgAdmin for actual database name")
        print("  - Wrong DB_PASSWORD in .env")
        print("    Fix: Update password in .env file")
        print("  - Wrong DB_HOST (if using remote DB)")
        return

    # ── Step 2: Check tables ───────────────────────────────
    try:
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        table_names = [r["table_name"] for r in tables]
        print(f"[2] TABLES ............... {table_names}")

        if "cases" not in table_names:
            print("    WARNING: 'cases' table does not exist!")
            print("    Fix: Run /start in the bot to trigger init_db()")
    except Exception as e:
        print(f"[2] TABLES ............... FAILED: {e}")

    # ── Step 3: Check columns ──────────────────────────────
    try:
        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'cases'
            ORDER BY ordinal_position
        """)
        if cols:
            print(f"[3] COLUMNS 'cases' ...... {len(cols)} columns found")
            for c in cols:
                flag = " <-- NOT NULL" if c["is_nullable"] == "NO" else ""
                print(f"    {c['column_name']:22s} {c['data_type']:15s}{flag}")
        else:
            print("[3] COLUMNS .............. table 'cases' is empty or missing")
    except Exception as e:
        print(f"[3] COLUMNS .............. FAILED: {e}")

    # ── Step 4: Test INSERT ────────────────────────────────
    print("")
    print("[4] TESTING INSERT ...")
    from datetime import datetime
    test_no = f"TEST-{datetime.now().strftime('%H%M%S')}"
    try:
        row = await conn.fetchrow("""
            INSERT INTO cases (
                case_no, tg_user_id, tg_username,
                platform, amount, coin, incident_time,
                wallet_addr, chain_type, tx_hash, contact
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            RETURNING id, case_no
        """,
            test_no, 999999, "test_user",
            "Test Platform", 5000.0, "USDT", "2026-01-15",
            "Unknown", "Unknown", "None", "test@email.com"
        )
        print(f"    INSERT ............... OK  id={row['id']}")
        await conn.execute("DELETE FROM cases WHERE case_no=$1", test_no)
        print(f"    CLEANUP .............. OK")
        print("")
        print("=" * 55)
        print("  RESULT: DATABASE IS WORKING CORRECTLY")
        print("  The error is likely in bot logic, not DB.")
        print("=" * 55)
    except Exception as e:
        print(f"    INSERT ............... FAILED")
        print(f"    Error: {e}")
        print("")
        print("=" * 55)
        print("  ROOT CAUSE FOUND:")
        print(f"  {e}")
        print("=" * 55)
        print("")
        print("  Common fixes:")
        print("  - 'null value in column X' -> missing NOT NULL column")
        print("    Fix: Run init_db() or restart bot with new database.py")
        print("  - 'duplicate key value' -> test_no collision (ignore)")
        print("  - 'invalid input syntax' -> data type mismatch")

    await conn.close()

asyncio.run(main())
