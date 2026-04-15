"""baseline: 历史表结构由 database.init_db() 创建；此后新变更请在本目录追加 revision。

已存在且由 init_db 维护的生产/预发库：接入 Alembic 时执行一次
  alembic stamp 001_baseline
勿在空库上仅 stamp 而不跑 init_db / 不应用后续 revision。

Revision ID: 001_baseline
Revises:
Create Date: 2026-04-02

"""
from typing import Sequence, Union

revision: str = "001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
