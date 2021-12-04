import inspect
import os
import sys
import io
import traceback
from contextlib import contextmanager

MISSING = object()
TRUE, FALSE = 'true', 'false'


def traceback_string(exception):
    return ''.join(traceback.format_tb(exception.__traceback__))


@contextmanager
def redirect_output(target=None):
    target = target or io.StringIO()
    original = (sys.stdout, sys.stderr)
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


def add_to_module(cls_or_func):
    setattr(sys.modules[cls_or_func.__module__], cls_or_func.__name__, cls_or_func)
    return cls_or_func


def get_typed_class_attrs(cls, base):
    class_attrs = {}
    for c in reversed(cls.__mro__):
        for name, attr in vars(c).items():
            if isinstance(attr, base):
                class_attrs[name] = attr
    return class_attrs


def count(seq, key):
    counter = 0
    for s in seq:
        if key(s):
            counter += 1
    return counter


if __name__ == '__main__':
    print(get_entry_file(True))
    print(get_entry_file(False))

