from datetime import datetime, timedelta, time
from functools import wraps, partial

from pycicle.tools.utils import TRUE, FALSE


class ParseError(ValueError):
    pass


def parse_error(on=True):
    def parse_error(func):
        if not on:
            return func

        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (TypeError, ValueError) as error:
                raise ParseError(str(error))

        return inner

    return parse_error


def parse_bool(arg,
               true_set=frozenset((TRUE, 'yes', 'true', 't', 'y', '1')),
               false_set=frozenset((FALSE, 'no', 'false', 'f', 'n', '0'))):
    if isinstance(arg, (bool, int)):
        return bool(arg)
    if arg.strip().lower() in true_set:
        return True
    if arg.strip().lower() in false_set:
        return False
    raise ValueError('Boolean value expected')


def encode_bool(val):
    return TRUE if val else FALSE


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


def parse_split(string, delimiter='"'):
    strings = []
    after = string
    while len(after):
        before, char, after = after.partition(delimiter)
        strings.extend(before.split())
        if char == delimiter:
            between, char, after = after.partition(delimiter)
            if char != delimiter:
                raise ValueError(f"parsing error in 'parse_split()': unmatched quotes ({delimiter}) in '{string}'")
            strings.append(between)
    return strings


def split_encode(strings, delimiter='"'):
    return ' '.join(quotify(s, delimiter, char=' ') for s in strings)


def quotify(string, delimiter='"', char=' '):
    if not char or string == '' or char in string:
        return f'{delimiter}{string}{delimiter}'
    return string


if __name__ == '__main__':
    in_strings = ['', '  ', 'a', ' a', ' a  ', 'a b', 'a "b c" d', 'a "b " d', 'a "" b', '""']
    for string in in_strings:
        decoded = parse_split(string)
        recoded = split_encode(decoded)
        print(' > '.join([string, str(decoded), recoded]), 'DIFFERENT' if string != recoded else '')
