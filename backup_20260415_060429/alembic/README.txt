Alembic 与 init_db 分工
-----------------------
- 现状：全量 DDL 仍在 database.init_db()（含 migrations 列表里的 ALTER）。
- 本目录 revision 001_baseline 为空操作，用于把「当前 schema 版本」记入 alembic_version。
- 已上线数据库首次接入：在目标库设置好 DB_* 或 DATABASE_URL 后执行
    alembic stamp 001_baseline
- 以后仅通过「新增 revision」改表（op.add_column / op.create_table 等），避免再往 init_db 堆 ALTER。
- 新环境可继续先 init_db() 再 stamp；或未来把基线迁成单一大 revision 后改为 alembic upgrade head（需单独规划）。
