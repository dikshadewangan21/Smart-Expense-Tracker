"""phase4 goals debts net worth

Revision ID: 8605b7acb86a
Revises: ff418f598160
Create Date: 2026-10-05 09:49:45.981152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8605b7acb86a'
down_revision: Union[str, None] = 'ff418f598160'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'account_valuations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('value', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'date'),
    )
    op.create_index(op.f('ix_account_valuations_account_id'), 'account_valuations', ['account_id'], unique=False)

    # Batch mode so the same migration runs on SQLite (which cannot ALTER ... ADD CONSTRAINT) and PostgreSQL.
    # Foreign keys are named so the downgrade can drop them.
    with op.batch_alter_table('transactions') as b:
        b.add_column(sa.Column('to_account_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_transactions_to_account_id', 'accounts', ['to_account_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('goal_contributions') as b:
        b.add_column(sa.Column('note', sa.String(length=200), nullable=True))

    with op.batch_alter_table('debts') as b:
        b.add_column(sa.Column('start_date', sa.Date(), nullable=True))
        b.add_column(sa.Column('bill_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_debts_bill_id', 'bills', ['bill_id'], ['id'], ondelete='SET NULL')

    # Existing payments (if any) reduced `remaining` by their full amount, so principal_paid = amount.
    with op.batch_alter_table('debt_payments') as b:
        b.add_column(sa.Column('principal_paid', sa.Numeric(precision=14, scale=2), nullable=True))
        b.add_column(sa.Column('transaction_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_debt_payments_transaction_id', 'transactions', ['transaction_id'], ['id'], ondelete='SET NULL')
    op.execute('UPDATE debt_payments SET principal_paid = amount WHERE principal_paid IS NULL')
    with op.batch_alter_table('debt_payments') as b:
        b.alter_column('principal_paid', existing_type=sa.Numeric(precision=14, scale=2), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('debt_payments') as b:
        b.drop_constraint('fk_debt_payments_transaction_id', type_='foreignkey')
        b.drop_column('transaction_id')
        b.drop_column('principal_paid')
    with op.batch_alter_table('debts') as b:
        b.drop_constraint('fk_debts_bill_id', type_='foreignkey')
        b.drop_column('bill_id')
        b.drop_column('start_date')
    with op.batch_alter_table('goal_contributions') as b:
        b.drop_column('note')
    with op.batch_alter_table('transactions') as b:
        b.drop_constraint('fk_transactions_to_account_id', type_='foreignkey')
        b.drop_column('to_account_id')
    op.drop_index(op.f('ix_account_valuations_account_id'), table_name='account_valuations')
    op.drop_table('account_valuations')
