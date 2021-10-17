import inspect
import os
import sys
from io import StringIO
from contextlib import contextmanager

MISSING = object()
DEFAULT = object()
TRUE, FALSE = 'true', 'false'


@contextmanager
def get_stdout():
    original = sys.stdout
    sys.stdout = StringIO()
    try:
        yield lambda: string
        string = sys.stdout.getvalue()
    finally:
        sys.stdout.close()
        sys.stdout = original


def get_entry_file(path=True):
    file_path = inspect.stack()[-1].filename
    if path:
        return os.path.abspath(file_path)
    return os.path.basename(file_path)


if __name__ == '__main__':
    print(get_entry_file(True))
    print(get_entry_file(False))

