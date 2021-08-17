from datetime import datetime, timedelta, time


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