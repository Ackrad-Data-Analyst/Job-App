"""Keep personal tables outside public Supabase access."""
from alembic import op
from careerpilot.models import Base
revision = '20_private_postgres'
down_revision = '9448f49c2491'
branch_labels = None
depends_on = None

def upgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    roles = set(op.get_bind().exec_driver_sql('SELECT rolname FROM pg_roles').scalars())
    for table in Base.metadata.tables:
        # Table names are static application identifiers, never owner input.
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC')
        for role in ['anon', 'authenticated']:
            if role in roles:
                op.execute(f'REVOKE ALL ON TABLE "{table}" FROM "{role}"')

def downgrade():
    # Intentionally retain privacy restrictions when rolling back this migration.
    pass
