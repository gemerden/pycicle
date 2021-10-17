import inspect
import os
import sys
import io
import traceback
from contextlib import contextmanager

MISSING = object()
DEFAULT = object()
TRUE, FALSE = 'true', 'false'


def traceback_string(exception):
    return ''.join(traceback.format_tb(exception.__traceback__))


@contextmanager
def redirect_output(target=None):
    target = target or io.StringIO()
    original = (sys.stdout,  sys.stderr)
    sys.stdout, sys.stderr = (target, target)
    try:
        yield target
    except BaseException as error:
        target.write(traceback_string(error))
        raise
    finally:
        sys.stdout, sys.stderr = original
        if hasattr(target, 'close'):
            target.close()


def get_entry_file(path=True):
    file_path = inspect.stack()[-1].filename
    if path:
        return os.path.abspath(file_path)
    return os.path.basename(file_path)


if __name__ == '__main__':
    print(get_entry_file(True))
    print(get_entry_file(False))

