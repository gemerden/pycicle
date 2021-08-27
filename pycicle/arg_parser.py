import json
import os
import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

from pycicle import arg_gui
from pycicle.tools import get_stdout, Codec, MISSING
from pycicle.parsers import parse_bool, encode_bool, encode_datetime, parse_datetime, encode_date, parse_date, \
    encode_time, parse_time, parse_timedelta, encode_timedelta


class ConfigError(ValueError):
    pass


@dataclass
class Argument(object):
    type: Callable
    many: Union[bool, int] = False
    positional: bool = False
    default: Any = None
    novalue: Any = MISSING
    required: bool = False
    valid: Callable[[Any], bool] = None
    callback: Callable[[Any, Namespace], Any] = None
    help: str = ""
    name: Union[str, None] = None  # set in __set_name__

    type_codecs = {
        bool: Codec(encode_bool, parse_bool),
        datetime: Codec(encode_datetime, parse_datetime),
        timedelta: Codec(encode_timedelta, parse_timedelta),
        date: Codec(encode_date, parse_date),
        time: Codec(encode_time, parse_time),
    }

    reserved = {'help'}

    def __post_init__(self):
        encode, decode = self.type_codecs.get(self.type, (None, None))
        self._encode = encode or str
        self._decode = decode or self.type
        self.flags = None

    def __set_name__(self, cls, name):
        self.name = name

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        try:
            return obj.__dict__[self.name]
        except KeyError:
            return self.default

    def __set__(self, obj, value):
        if self.callback:
            self.callback(value, obj)
        obj.__dict__[self.name] = self.validate(value)

    def __delete__(self, obj):
        obj.__dict__.pop(self.name, None)

    def check_config(self):
        """
        Called in __init_subclass__ of owner class because self.name must be set to give clearer error messages and
        python __set_name__ changes all exceptions to (somewhat vague) RuntimeError.
        """
        self.default = self.validate(self.default, _config=True)
        if self.novalue is not MISSING:
            if self.positional:
                raise ConfigError(f"argument '{self.name}' is flag only and cannot be positional")
            self.novalue = self.validate(self.novalue, _config=True)

    def encode(self, value):
        if value is None:
            return ''
        if self.many:
            return [self._encode(v) for v in value]
        return self._encode(value)

    def decode(self, value):
        if self.type is not str and value == '':
            return None
        if self.many:
            return [self._decode(v) for v in value]
        return self._decode(value)

    def validate(self, value, _config=False):
        exception_class = ConfigError if _config else ValueError
        if value is None or value is MISSING:
            if not _config and self.required:
                raise ValueError(f"argument value '{self.name}' is required")
            return value
        if self.many is not False:
            if not isinstance(value, (list, tuple)):
                raise exception_class(f"argument value for '{self.name}' is not a list or tuple")
            value = list(value)
        if not isinstance(self.many, bool):
            if len(value) != self.many:
                raise exception_class(f"argument value for '{self.name}' is not of correct length {self.many}")
        try:
            if isinstance(value, str) or (self.many is not False and all(isinstance(v, str) for v in value)):
                value = self.decode(value)
            if value is not None and self.valid and not self.valid(value):
                raise exception_class(f"invalid value for argument '{self.name}'")
        except TypeError as e:
            raise exception_class(str(e))
        return value

    def _get_name_or_flag(self, seen) -> tuple:
        if self.name in self.reserved:
            raise ConfigError(f"argument name '{self.name}' is reserved")

        if self.positional:
            if not all(arg.positional for arg in seen.values()):
                raise ConfigError(f"cannot place positional argument '{self.name}' after non-positional arguments")
            return self.name,
        else:
            seen_shorts = set(a[0] for a in seen) | set(a[0] for a in self.reserved)
            if self.name[0] in seen_shorts:
                if len(self.name) == 1:
                    raise ConfigError(f"'-{self.name[0]}' already exist as a short argument name")
                return '--' + self.name,
            return '--' + self.name, '-' + self.name[0]

    def add_to_parser(self, parser, seen):
        flags = self._get_name_or_flag(seen)
        kwargs = dict(type=self._decode,
                      default=self.default,
                      nargs=None,
                      help=self.help)
        if self.many is True:
            if self.required:
                kwargs.update(nargs='+')
            else:
                kwargs.update(nargs='*')
        elif self.many is not False:
            kwargs.update(nargs=self.many)
        elif self.positional:
            if not self.required:
                kwargs.update(nargs='?')
        else:
            kwargs.update(required=self.required)
        if self.novalue is not MISSING:
            kwargs.update(action='store_const',
                          const=self.novalue)
            kwargs.pop('type', None)
            kwargs.pop('nargs', None)
        self.flags = () if self.positional else flags
        try:
            parser.add_argument(*flags, **kwargs)
        except Exception as e:
            raise ConfigError(str(e))

    def _cmd_flag(self, short=False):
        """ return flag e.g. '--version', '-v' if short"""
        if len(self.flags) == 0:  # ~ positional is True
            return ''
        if len(self.flags) == 1:
            return self.flags[0]
        return self.flags[0] if short else self.flags[1]

    def _cmd_value(self, value):
        if self.many:
            return ' '.join(self.encode(value))
        return self.encode(value)

    def cmd(self, obj, short=False):
        value = self.__get__(obj)
        if self.novalue is not MISSING:
            if value == self.novalue:
                return self._cmd_flag(short)
            return ''  # value will be the default
        cmd_value = self._cmd_value(value)
        if cmd_value == '':
            return ''
        if self.positional:
            return cmd_value
        return f"{self._cmd_flag(short)} {cmd_value}"

    def to_json(self, obj):
        value = self.__get__(obj)
        if value is None:
            return None
        return self.encode(value)

    def to_string_dict(self, names=None):
        def string(item):
            try:
                return item.__name__
            except AttributeError:
                return str(item)

        if names is None:
            names = list(self.__dict__)
        return {name: string(getattr(self, name)) for name in names}

    def check_required(self, obj):
        value = self.__get__(obj)
        if self.required and value is None and self.default is not None:
            return False
        return True



class ArgParser(Mapping):
    _parser_class = ArgumentParser
    _arg_parser = None  # set in __init_subclass__
    _arguments = None  # set in __init_subclass__

    _reserved = {'help'}  # -h, --help is already used by argparse itself

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._arg_parser = cls._parser_class(**kwargs)
        cls._arguments = cls._get_arguments()
        seen = {}
        for arg in cls._arguments:
            arg.add_to_parser(cls._arg_parser, seen)
            seen[arg.name] = arg
        cls._arg_names = frozenset(seen)

    @classmethod
    def _get_arguments(cls):
        arguments = {}  # dict to override arguments with same name in base classes
        for c in reversed(cls.__mro__):
            for name, arg in vars(c).items():
                if isinstance(arg, Argument):
                    arg.check_config()  # see comment in method
                    arguments[arg.name] = arg
        return tuple(arguments.values())

    @classmethod
    def _get_defaults(cls):
        return {arg.name: arg.default for arg in cls._arguments}

    @classmethod
    def _get_def_string(cls):
        line_end = '\n\t'
        return f"{line_end}{line_end.join(map(str, cls._arguments))}"

    @classmethod
    def _cmd_help(cls):
        with get_stdout() as cmd_help:
            cls._arg_parser.print_help()
        lines = [l.strip() for l in cmd_help().split('\n')]
        return '\n\t'.join(lines)

    @classmethod
    def _as_value_dict(cls, json_dict):
        return {arg.name: arg.decode(json_dict[arg.name]) for arg in cls._arguments}

    @classmethod
    def _load(cls, filename: str, mode: str = 'r'):
        with open(filename, mode) as f:
            json_dict = json.load(f)
        return cls(cls._as_value_dict(json_dict))

    def __init__(self,
                 args: Union[str, Sequence, Mapping, None] = None,
                 target: Callable = None,
                 use_gui: bool = True):
        if use_gui and self._no_arguments(args):
            self._run_gui(target)
        else:
            self._init_parse(args)
            if target:
                self(target)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __iter__(self) -> Iterable:
        yield from self.__dict__

    def __getitem__(self, key: str):
        return self.__dict__[key]

    def _no_arguments(self, args):
        return not args and len(sys.argv) == 1

    def _run_gui(self, target):
        arg_gui.ArgGui(parser=self, target=target).mainloop()

    def _init_parse(self, args):
        if args is None and "PYTEST_CURRENT_TEST" in os.environ:
            args = sys.argv[2:]  # fix for running tests with pytest (extra cmd line arg)
        elif isinstance(args, Mapping):
            self._update(args)
            args = self._command()
        self._parse_command(args)

    def _parse_command(self, args):
        if isinstance(args, str):
            args = [a.strip() for a in args.split()]
        try:
            parsed = self._arg_parser.parse_args(args)
        except SystemExit as e:  # intercept when e.g. called with --help
            if e.code not in (None, 0):
                raise
        else:
            self._update(parsed.__dict__)

    def _update(self, kwargs):
        new_kwargs = self._get_defaults()
        new_kwargs.update(self.__dict__)
        new_kwargs.update(kwargs)
        self.__dict__.clear()
        for name, value in new_kwargs.items():
            setattr(self, name, value)

    def __call__(self, target: Callable) -> Any:
        if not target:
            raise ValueError(f"cannot call 'None' target")
        for arg in self._arguments:
            if not arg.check_required(self):
                raise ValueError(f"missing required argument '{arg.name}'")
        self._parse_command(self._command())
        return target(**self)

    def _command(self, short=False, prog=False):
        cmds = [arg.cmd(self, short) for arg in self._arguments]
        arg_string = ' '.join(cmd for cmd in cmds if cmd)
        if prog:
            return f"{os.path.basename(sys.argv[0])} {arg_string}"
        return arg_string

    def _as_json_dict(self):
        return {arg.name: arg.encode(getattr(self, arg.name)) for arg in self._arguments}

    def _save(self, filename: str, mode: str = 'w'):
        with open(filename, mode) as f:
            f.write(json.dumps(self._as_json_dict()))

    def __str__(self) -> str:
        return json.dumps(self.__dict__, indent=4)

    def __repr__(self) -> str:
        return json.dumps(self.__dict__, indent=4)


if __name__ == '__main__':
    pass
