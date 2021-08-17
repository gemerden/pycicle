import sys
from collections import namedtuple
from datetime import datetime, timedelta, time
from io import StringIO
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def get_stdout():
    backup = sys.stdout
    sys.stdout = StringIO()
    yield lambda: string
    string = sys.stdout.getvalue()
    sys.stdout.close()
    sys.stdout = backup


Codec = namedtuple('Codec', ['encode', 'decode'])


class FileFolderBase(str):
    exists = False
    does_exist = None

    def __new__(cls, string=''):
        if not string or (isinstance(string, str) and not string.strip()):
            return super().__new__(cls)
        path = Path(string)
        if cls.exists and not cls.does_exist(path):
            raise ValueError(f"file: {str(path)} does not exist")
        return super().__new__(cls, path)

    def __str__(self):
        return self.replace('\\\\', '/')


class FileBase(FileFolderBase):
    extensions = ()
    does_exist = Path.is_file

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        extensions = set()
        for ext in cls.extensions:
            ext = ext.strip()
            if ext.startswith('.'):
                ext = ext[1:]
            extensions.add(ext)
        cls.extensions = frozenset(extensions)

    def __new__(cls, string=''):
        _, _, ext = string.rpartition('.')
        if cls.extensions and ext not in cls.extensions:
            raise ValueError(f"incorrect extension for file: {string}")
        return super().__new__(cls, string)


class FolderBase(FileFolderBase):
    does_exist = Path.is_dir


def File(*extensions, exists=False):
    return type('File', (FileBase,), dict(exists=exists, extensions=extensions))


def Folder(exists=False):
    return type('Folder', (FolderBase,), dict(exists=exists))


class ChoiceBase(object):
    choices = ()

    def __new__(cls, value=None):
        if value is None:
            value = cls.choices[0]
        elif isinstance(value, str):
            value = cls.__bases__[1](value)
        if value not in cls.choices:
            raise ValueError(f"value '{str(value)}' is not a choice in {cls.choices}")
        return super().__new__(cls, value)


def Choice(*choices):
    if not len(choices):
        raise ValueError(f"cannot define Choice without choices")
    if any(type(c) != type(choices[0]) for c in choices):
        raise ValueError(f"all choices must be of same class")
    return type('Choice', (ChoiceBase, type(choices[0])), {'choices': choices})


def parse_bool(arg,
               true_set=frozenset(('yes', 'true', 't', 'y', '1')),
               false_set=frozenset(('no', 'false', 'f', 'n', '0'))):
    if isinstance(arg, (bool, int)):
        return bool(arg)
    if arg.lower() in true_set:
        return True
    if arg.lower() in false_set:
        return False
    raise ValueError('Boolean value expected')


def encode_bool(val):
    return '1' if val else '0'


def encode_datetime(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_datetime(string):
    return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S")


def encode_date(d):
    return d.strftime("%Y-%m-%d")


def parse_date(string):
    return datetime.strptime(string, "%Y-%m-%d").date()


def encode_time(t, sep=":"):
    return t.strftime(sep.join(["%H", "%M", "%S"]))


def parse_time(string):
    return datetime.strptime(string, "%H:%M:%S").time()


def parse_timedelta(string):
    h, m, s = [s.strip() for s in string.split(':')]
    return timedelta(hours=int(h), minutes=int(m), seconds=float(s))


def encode_timedelta(td):
    secs = td.total_seconds()
    hours, seconds = divmod(secs, 3600)
    minutes, seconds = divmod(seconds, 60)
    seconds, secpart = divmod(seconds, 1)
    h = str(int(hours)).zfill(2)
    m = str(int(minutes)).zfill(2)
    s = str(int(seconds)).zfill(2)
    p = str(secpart).split('.')[1]
    return f"{h}:{m}:{s}.{p}"


def seconds_to_time_string(seconds):
    if seconds is None:
        return ""
    return encode_time(seconds_to_time(seconds))


def seconds_to_time(secs):
    secs = int(secs + 0.5)
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return time(h % 24, m, s)  # spills over to next day


def seconds_to_timedelta_string(seconds):
    if seconds is None:
        return ""
    if seconds < 0:
        return "-" + str(timedelta(seconds=-seconds))
    return str(timedelta(seconds=seconds))


def datetime_to_string(dt):
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def short_datetime_to_string(dt):
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def time_to_string(t):
    return str(t)


def string_to_datetime(string):
    if string is None:
        return None
    try:
        return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S")


if __name__ == '__main__':
    file = File('.py', exists=True)
    f = file('D:/documents/_Code_/_repos_/clapy/clapy/temp/sample.py')
    print(type(file))
    print(file)
    print(f)

    choice = Choice(1, 2, 3)
    choice(1)
    choice(4)
