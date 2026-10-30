from alembic import context
from careerpilot.config import engine
from careerpilot.models import Base

with engine().connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
