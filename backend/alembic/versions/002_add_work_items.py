"""Add work_items table and update visit_sku_actions for new workflow.

Revision ID: 002_add_work_items
Revises:
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa


revision = '002_add_work_items'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create work_items table
    op.create_table(
        'work_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=False),
        sa.Column('segment', sa.String(length=30), nullable=False),
        sa.Column('before_photo_id', sa.Integer(), nullable=True),
        sa.Column('after_photo_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='created'),
        sa.Column('prices_on_gondola', sa.Boolean(), nullable=True),
        sa.Column('pop_material_present', sa.Boolean(), nullable=True),
        sa.Column('product_presentable', sa.Boolean(), nullable=True),
        sa.Column('gondola_space_gained', sa.Boolean(), nullable=True),
        sa.Column('condition_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['visit_id'], ['store_visits.id'], ),
        sa.ForeignKeyConstraint(['before_photo_id'], ['visit_photos.id'], ),
        sa.ForeignKeyConstraint(['after_photo_id'], ['visit_photos.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_work_items_id', 'work_items', ['id'], unique=False)
    op.create_index('ix_work_items_segment', 'work_items', ['segment'], unique=False)

    # Add segment column to visit_photos
    op.add_column('visit_photos', sa.Column('segment', sa.String(length=30), nullable=True))
    op.create_index('ix_visit_photos_segment', 'visit_photos', ['segment'], unique=False)

    # Add new columns to visit_sku_actions
    op.add_column('visit_sku_actions', sa.Column('work_item_id', sa.Integer(), nullable=True))
    op.add_column('visit_sku_actions', sa.Column('estado_gondola', sa.String(length=20), nullable=True))
    op.add_column('visit_sku_actions', sa.Column('trabajo', sa.String(length=20), nullable=True))
    op.add_column('visit_sku_actions', sa.Column('orden_cantidad_cajas', sa.Integer(), nullable=True))
    op.add_column('visit_sku_actions', sa.Column('orden_fecha_llegada', sa.DateTime(), nullable=True))

    op.create_foreign_key(
        'fk_visit_sku_actions_work_item_id',
        'visit_sku_actions',
        'work_items',
        ['work_item_id'],
        ['id']
    )

    # Make action_type nullable (for backwards compatibility)
    op.alter_column('visit_sku_actions', 'action_type', nullable=True)


def downgrade():
    op.drop_constraint('fk_visit_sku_actions_work_item_id', 'visit_sku_actions', type_='foreignkey')
    op.drop_column('visit_sku_actions', 'orden_fecha_llegada')
    op.drop_column('visit_sku_actions', 'orden_cantidad_cajas')
    op.drop_column('visit_sku_actions', 'trabajo')
    op.drop_column('visit_sku_actions', 'estado_gondola')
    op.drop_column('visit_sku_actions', 'work_item_id')

    op.drop_index('ix_visit_photos_segment', table_name='visit_photos')
    op.drop_column('visit_photos', 'segment')

    op.drop_index('ix_work_items_segment', table_name='work_items')
    op.drop_index('ix_work_items_id', table_name='work_items')
    op.drop_table('work_items')

    op.alter_column('visit_sku_actions', 'action_type', nullable=False)
