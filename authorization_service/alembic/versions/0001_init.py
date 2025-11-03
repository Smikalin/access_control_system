from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conflicting_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_code_a", sa.String(length=100), nullable=False),
        sa.Column("group_code_b", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("group_code_a", "group_code_b", name="uq_conflict_pair"),
    )

    # seed conflicts: DEVELOPER vs OWNER
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO conflicting_groups(group_code_a, group_code_b) VALUES (:a, :b) ON CONFLICT DO NOTHING"
        ),
        {"a": "DEVELOPER", "b": "OWNER"},
    )


def downgrade() -> None:
    op.drop_table("conflicting_groups")
