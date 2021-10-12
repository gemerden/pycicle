import sys
from io import StringIO
from contextlib import contextmanager


MISSING = object()
DEFAULT = object()


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

