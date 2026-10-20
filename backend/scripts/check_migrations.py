"""Exercise upgrade/downgrade/upgrade on a newly created disposable SQLite database."""
import os
import subprocess
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
scratch = root / '.test-data'
scratch.mkdir(exist_ok=True)
target = scratch / f'migration-{uuid.uuid4()}.db'
environment = {**os.environ, 'DATABASE_URL': f'sqlite:///{target.as_posix()}'}
for arguments in (['upgrade', 'head'], ['downgrade', 'base'], ['upgrade', 'head'], ['check']):
    subprocess.run([sys.executable, '-m', 'alembic', *arguments], cwd=root, env=environment, check=True)
print('Migration upgrade, downgrade, re-upgrade and metadata check passed on disposable SQLite database')
