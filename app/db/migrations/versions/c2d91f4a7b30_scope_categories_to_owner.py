"""scope categories to their owner

Categories were global: a single shared table with a unique `name`, which let
any authenticated user list and delete everyone else's categories. This adds
`user_id` and moves uniqueness to (user_id, name), so each user has their own
category list.

Existing rows are backfilled by attributing each category to the user who
actually used it (via budgets, then transactions). Categories referenced by
nobody are left unassigned and deleted at the end -- they carry no data.

Revision ID: c2d91f4a7b30
Revises: b5a7caabe252
Create Date: 2026-09-29

"""
import sqlalchemy as sa
from alembic import op

revision = "c2d91f4a7b30"
down_revision = "b5a7caabe252"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable first so the backfill below has somewhere to put a value.
    op.add_column("categories", sa.Column("user_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_categories_user_id"), "categories", ["user_id"])

    # Drop global uniqueness on `name` before backfilling: several users may
    # legitimately end up owning a category with the same name.
    with op.batch_alter_table("categories") as batch:
        batch.drop_constraint("uq_categories_name", type_="unique")

    # Attribute each category to a user who referenced it. Budgets are checked
    # before transactions because they are the stronger signal. Ties are broken
    # by taking the lowest user id, so the result is deterministic.
    op.execute(
        """
        UPDATE categories
           SET user_id = (
               SELECT MIN(b.user_id) FROM budgets b WHERE b.category_id = categories.id
           )
         WHERE user_id IS NULL
           AND EXISTS (SELECT 1 FROM budgets b WHERE b.category_id = categories.id)
        """
    )
    op.execute(
        """
        UPDATE categories
           SET user_id = (
               SELECT MIN(t.user_id) FROM transactions t WHERE t.category_id = categories.id
           )
         WHERE user_id IS NULL
           AND EXISTS (SELECT 1 FROM transactions t WHERE t.category_id = categories.id)
        """
    )

    # Nobody used these, so they hold no user data. Remove them before the
    # NOT NULL constraint, which they could not satisfy.
    op.execute("DELETE FROM categories WHERE user_id IS NULL")

    # One batch rebuild: SQLite cannot ALTER constraints in place (it recreates
    # the table), and on Postgres this is clearer than three separate ops.
    with op.batch_alter_table("categories") as batch:
        batch.create_foreign_key("fk_categories_user_id", "users", ["user_id"], ["id"])
        batch.alter_column("user_id", existing_type=sa.String(), nullable=False)
        batch.create_unique_constraint("uq_category_user_name", ["user_id", "name"])


def downgrade() -> None:
    # Back to a global `name` and no owner. The original constraint was unique
    # on `name` alone, which per-user duplicates would violate, so colliding
    # names are suffixed with the owner id first -- otherwise the downgrade
    # would fail halfway with a constraint violation.
    op.add_column("categories", sa.Column("name_legacy", sa.String(), nullable=True))
    op.execute("UPDATE categories SET name_legacy = name")
    op.execute(
        """
        UPDATE categories
           SET name_legacy = name || ' (' || user_id || ')'
         WHERE name IN (
             SELECT name FROM categories GROUP BY name HAVING COUNT(*) > 1
         )
        """
    )
    op.drop_index(op.f("ix_categories_user_id"), table_name="categories")

    # Everything structural in one batch: SQLite cannot ALTER constraints or
    # drop/rename columns in place, and a single rebuild avoids intermediate
    # states that would be invalid.
    with op.batch_alter_table("categories") as batch:
        batch.drop_constraint("uq_category_user_name", type_="unique")
        batch.drop_constraint("fk_categories_user_id", type_="foreignkey")
        batch.drop_column("name")
        batch.alter_column("name_legacy", new_column_name="name", nullable=False)
        batch.create_unique_constraint("uq_categories_name", ["name"])
        batch.drop_column("user_id")