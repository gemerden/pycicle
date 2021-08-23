import json
import os
import sys
from argparse import ArgumentParser, Action, Namespace
from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from functools import partial
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

from pycicle import arg_app
from pycicle.tools import get_stdout, Codec
from pycicle.parsers import parse_bool, encode_bool, encode_datetime, parse_datetime, encode_date, parse_date, \
    encode_time, parse_time, parse_timedelta, encode_timedelta


@dataclass
class Argument(object):
    type: Callable
    many: Union[bool, int] = False
    positional: bool = False
    default: Any = None
    required: bool = False
    valid: Callable = None
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

    help_template = "{name} {args}: \t\t\t{type}, \tdefault: {default}, \thelp: {help}"
    nohelp_template = "{name} {args}: \t\t\t{type}, \tdefault: {default}"

    def __post_init__(self):
        encode, decode = self.type_codecs.get(self.type, (None, None))
        self._encode = encode or str
        self._decode = decode or self.type

    def __set_name__(self, cls, name):
        self.name = name
        self.default = self.validate(self.default, _default=True)

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        try:
            return obj.__dict__[self.name]
        except KeyError:
            return self.default

    def __set__(self, obj, value):
        obj.__dict__[self.name] = self.validate(value)

    def __delete__(self, obj):
        obj.__dict__.pop(self.name, None)

    def encode(self, value):
        if value is None:
            return ''
        if self.many:
            return [self._encode(v) for v in value]
        return self._encode(value)

    def decode(self, value):
        if value == '':
            return None
        if self.many:
            return [self._decode(v) for v in value]
        return self._decode(value)

    def validate(self, value, _default=False):
        if value in (None, ""):
            if not _default and self.required:
                raise ValueError(f"argument value '{self.name}' is required")
            return None
        if not isinstance(self.many, bool):
            if len(value) != self.many:
                raise ValueError(f"argument value for '{self.name}' is not of correct length {self.many}")
        if isinstance(value, str) or (self.many is not False and all(isinstance(v, str) for v in value)):
            value = self.decode(value)
        if value is not None and self.valid and not self.valid(value):
            raise ValueError(f"invalid value for argument '{self.name}'")
        return value

    def _get_name_or_flag(self, seen) -> tuple:
        if self.name in self.reserved:
            raise ValueError(f"argument name '{self.name}' is reserved")

        if self.positional:
            if not all(arg.positional for arg in seen.values()):
                raise ValueError(f"cannot place positional argument '{self.name}' after non-positional arguments")
        else:
            seen_shorts = set(a[0] for a in seen) | set(a[0] for a in self.reserved)
            if self.name[0] in seen_shorts:
                if len(self.name) == 1:
                    raise ValueError(f"'-{self.name[0]}' already exist as a short argument name")
                return '--' + self.name,
            return '-' + self.name[0], '--' + self.name
        return self.name,

    def add_to_parser(self, parser, seen):
        args = self._get_name_or_flag(seen)
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
        if self.callback:
            kwargs.update(action=partial(CallbackAction,
                                         callback=self.callback))
        self.args = () if self.positional else args
        parser.add_argument(*args, **kwargs)

    def cmd_key(self, short=False):
        """ return string e.g. '--version', '-v'"""
        if len(self.args) == 0:
            return ''
        if len(self.args) == 1:
            return self.args[0]
        return self.args[0] if short else self.args[1]

    def cmd_value(self, obj):
        value = self.__get__(obj)
        if self.many:
            return ' '.join(self.encode(value))
        return self.encode(value)

    def to_json(self, obj):
        value = self.__get__(obj)
        if value is None:
            return None
        return self.encode(value)

    def check_required(self, obj):
        value = self.__get__(obj)
        if self.required and value is None and self.default is not None:
            return False
        return True

    def __str__(self):
        def get_name(arg):
            try:
                return arg.__name__
            except AttributeError:
                return str(arg)

        if self.help.strip():
            return self.help_template.format(**{n: get_name(v) for n, v in self.__dict__.items()})
        return self.nohelp_template.format(**{n: get_name(v) for n, v in self.__dict__.items()})

    def __repr__(self):
        return super().__str__()


class CallbackAction(Action):
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        self.callback(values, namespace)


class ArgParser(Mapping):
    _parser_class = ArgumentParser
    _arg_parser = None  # set in __init_subclass__
    _arguments = None  # set in __init_subclass__

    _reserved = {'help'}  # -h, --help is already used by argparse

    _template = \
        """
        {title}
        _________________________________________________________________________________
        {original}
        
        Definitions:
        _________________________________________________________________________________
        {definitions}
        
        
        Command Line:
        _________________________________________________________________________________
        
        {parser_help}
        """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._arg_parser = cls._parser_class(**kwargs)
        cls._arguments = cls._get_arguments()
        seen = {}
        for arg in cls._arguments:
            arg.add_to_parser(cls._arg_parser, seen)
            seen[arg.name] = arg
        cls._arg_names = frozenset(seen)
        cls._extend_doc()

    @classmethod
    def _get_arguments(cls):
        arguments = {}
        for c in reversed(cls.__mro__):
            for name, arg in vars(c).items():
                if isinstance(arg, Argument):
                    arguments[arg.name] = arg  # overriding arguments with same name in base classes
        return tuple(arguments.values())

    @classmethod
    def _get_defaults(cls):
        return {arg.name: arg.default for arg in cls._arguments}

    @classmethod
    def _get_def_string(cls):
        line_end = '\n\t'
        return f"{line_end}{line_end.join(map(str, cls._arguments))}"

    @classmethod
    def _parser_help(cls):
        with get_stdout() as cmd_help:
            cls._arg_parser.print_help()
        lines = [l.strip() for l in cmd_help().split('\n')]
        return '\n\t'.join(lines)

    @classmethod
    def _extend_doc(cls):
        cls.__doc__ = cls._template.format(title=cls.__name__,
                                           original=cls.__doc__,
                                           definitions=cls._get_def_string(),
                                           parser_help=cls._parser_help())

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
                 use_app: bool = True):
        if use_app and self._no_arguments(args):
            self._run_app(target)
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

    def _run_app(self, target):
        arg_app.ArgApp(parser=self, target=target).mainloop()

    def _init_parse(self, args):
        if args is None and "PYTEST_CURRENT_TEST" in os.environ:
            args = sys.argv[2:]  # fix for running tests with pytest (extra cmd line arg)
        elif isinstance(args, Mapping):
            self._fill(args)
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
            self._fill(parsed.__dict__)

    def _fill(self, kwargs):
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

    def _command(self, short=False, _no_prog=True):
        items = []
        for arg in self._arguments:
            cmd_key, cmd_value = arg.cmd_key(short), arg.cmd_value(self)
            if cmd_value:
                items.append(f"{cmd_key} {cmd_value}")
        if _no_prog:
            return ' '.join(items).strip()
        program = os.path.basename(sys.argv[0])
        return f"{program} {' '.join(items).strip()}".strip()

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