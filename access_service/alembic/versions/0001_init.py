from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "accesses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "right_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "group_accesses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("right_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "access_id",
            sa.Integer(),
            sa.ForeignKey("accesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("group_id", "access_id", name="uq_group_access"),
    )
    op.create_table(
        "resource_accesses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resource_id",
            sa.Integer(),
            sa.ForeignKey("resources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "access_id",
            sa.Integer(),
            sa.ForeignKey("accesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("resource_id", "access_id", name="uq_resource_access"),
    )
    op.create_table(
        "user_accesses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column(
            "access_id",
            sa.Integer(),
            sa.ForeignKey("accesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "access_id", name="uq_user_access"),
    )
    op.create_index("ix_user_access_user_id", "user_accesses", ["user_id"])
    op.create_table(
        "user_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("right_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_group"),
    )
    op.create_index("ix_user_group_user_id", "user_groups", ["user_id"])

    # seed minimal data
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO accesses(code, description) VALUES ('DB_READ', 'Read-only to DB'), ('DB_WRITE', 'Write to DB'), ('API_KEY', 'Public API key') ON CONFLICT DO NOTHING"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO right_groups(code, description) VALUES ('DEVELOPER', 'Developer role'), ('DB_ADMIN', 'Database admin'), ('OWNER', 'Owner role') ON CONFLICT DO NOTHING"
        )
    )
    # Map group->access
    conn.execute(
        sa.text(
            "INSERT INTO group_accesses(group_id, access_id) SELECT g.id, a.id FROM right_groups g, accesses a WHERE g.code='DEVELOPER' AND a.code IN ('API_KEY') ON CONFLICT DO NOTHING"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO group_accesses(group_id, access_id) SELECT g.id, a.id FROM right_groups g, accesses a WHERE g.code='DB_ADMIN' AND a.code IN ('DB_READ','DB_WRITE') ON CONFLICT DO NOTHING"
        )
    )

    # resource sample
    conn.execute(
        sa.text(
            "INSERT INTO resources(name, description) VALUES ('db_cluster', 'Main DB cluster'), ('public_api', 'External API') ON CONFLICT DO NOTHING"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO resource_accesses(resource_id, access_id) SELECT r.id, a.id FROM resources r, accesses a WHERE r.name='db_cluster' AND a.code='DB_READ' ON CONFLICT DO NOTHING"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO resource_accesses(resource_id, access_id) SELECT r.id, a.id FROM resources r, accesses a WHERE r.name='public_api' AND a.code='API_KEY' ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_user_group_user_id", table_name="user_groups")
    op.drop_table("user_groups")
    op.drop_index("ix_user_access_user_id", table_name="user_accesses")
    op.drop_table("user_accesses")
    op.drop_table("resource_accesses")
    op.drop_table("group_accesses")
    op.drop_table("right_groups")
    op.drop_table("accesses")
    op.drop_table("resources")
