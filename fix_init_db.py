#!/usr/bin/env python3
"""
修复版本的数据库初始化脚本
使用单个连接而不是连接池来避免 Windows 网络问题
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def create_single_connection():
    """创建单个数据库连接"""
    return await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "weiquan_bot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )

async def init_db_single_connection():
    """使用单个连接初始化数据库"""
    print("🔄 开始初始化本地数据库（单连接模式）...")
    
    conn = None
    try:
        # 创建连接
        print("1️⃣ 创建数据库连接...")
        conn = await create_single_connection()
        print("✅ 数据库连接成功")
        
        # 启用 UUID 扩展
        print("2️⃣ 启用 UUID 扩展...")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
        print("✅ UUID 扩展已启用")
        
        # 创建案件主表
        print("3️⃣ 创建案件主表...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                case_no       TEXT UNIQUE NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                updated_at    TIMESTAMPTZ DEFAULT NOW(),

                -- 用户信息
                tg_user_id    BIGINT NOT NULL,
                tg_username   TEXT,

                -- 案件详情
                platform      TEXT NOT NULL,
                amount        NUMERIC(20,6),
                coin          TEXT,
                incident_time TEXT,
                wallet_addr   TEXT,
                chain_type    TEXT,
                tx_hash       TEXT,
                contact       TEXT,

                -- 状态管理
                status        TEXT DEFAULT '待初步审核',
                admin_notes   TEXT,

                -- 风险评分
                risk_score    INTEGER DEFAULT 0,
                risk_label    TEXT DEFAULT '未评估'
            );
        """)
        print("✅ cases 表创建成功")
        
        # 创建证据文件表
        print("4️⃣ 创建证据文件表...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS evidences (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                case_id     UUID REFERENCES cases(id) ON DELETE CASCADE,
                uploaded_at TIMESTAMPTZ DEFAULT NOW(),
                file_type   TEXT,
                file_id     TEXT,
                file_name   TEXT,
                description TEXT
            );
        """)
        print("✅ evidences 表创建成功")
        
        # 创建审计日志表
        print("5️⃣ 创建审计日志表...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id          BIGSERIAL PRIMARY KEY,
                logged_at   TIMESTAMPTZ DEFAULT NOW(),
                actor_type  TEXT,
                actor_id    TEXT,
                action      TEXT NOT NULL,
                target_id   TEXT,
                detail      TEXT
            );
        """)
        print("✅ audit_logs 表创建成功")
        
        # 创建状态变更历史表
        print("6️⃣ 创建状态变更历史表...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                id          BIGSERIAL PRIMARY KEY,
                case_id     UUID REFERENCES cases(id) ON DELETE CASCADE,
                changed_at  TIMESTAMPTZ DEFAULT NOW(),
                old_status  TEXT,
                new_status  TEXT,
                changed_by  TEXT,
                note        TEXT
            );
        """)
        print("✅ status_history 表创建成功")
        
        # 创建案件数字签名表
        print("7️⃣ 创建案件数字签名表...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS case_signatures (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                case_no      TEXT NOT NULL,
                tg_user_id   BIGINT NOT NULL,
                signed_at    TIMESTAMPTZ DEFAULT NOW(),
                signature_hex TEXT NOT NULL,
                ip_address  TEXT,
                auth_ref     TEXT,
                UNIQUE(case_no)
            );
        """)
        print("✅ case_signatures 表创建成功")
        
        # 创建用户 PIN 表
        print("8️⃣ 创建用户 PIN 表...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_pins (
                tg_user_id  BIGINT PRIMARY KEY,
                pin_hash    TEXT NOT NULL,
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        print("✅ user_pins 表创建成功")
        
        # 创建更新触发器
        print("9️⃣ 创建更新触发器...")
        await conn.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
            $$ LANGUAGE plpgsql;
        """)
        await conn.execute("""
            DROP TRIGGER IF EXISTS trg_cases_updated ON cases;
            CREATE TRIGGER trg_cases_updated
            BEFORE UPDATE ON cases
            FOR EACH ROW EXECUTE PROCEDURE update_updated_at();
        """)
        print("✅ 触发器创建成功")
        
        # 创建索引
        print("🔟 创建索引...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_cases_case_no ON cases(case_no)",
            "CREATE INDEX IF NOT EXISTS idx_cases_tg_user_id ON cases(tg_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_case_signatures_case_no ON case_signatures(case_no)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logged ON audit_logs(logged_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidences(case_id)"
        ]
        
        for idx_sql in indexes:
            await conn.execute(idx_sql)
        print("✅ 索引创建成功")
        
        # 验证表创建
        print("1️⃣1️⃣ 验证表创建...")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        print(f"✅ 成功创建 {len(tables)} 个表:")
        for table in tables:
            print(f"   - {table['table_name']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if conn:
            await conn.close()
            print("✅ 数据库连接已关闭")

if __name__ == "__main__":
    success = asyncio.run(init_db_single_connection())
    if success:
        print("\n🎉 数据库初始化完成！现在可以运行 bot.py")
        print("💡 如果 bot.py 仍有连接池问题，可以修改 database.py 中的连接池参数")
    else:
        print("\n❌ 初始化失败，请检查错误信息")
    
    sys.exit(0 if success else 1)
