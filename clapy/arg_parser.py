import json
import os
import sys
from argparse import ArgumentParser, Action, Namespace
from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from functools import partial
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

from clapy import arg_app
from tools import get_stdout, Codec
from parsers import parse_bool, encode_bool, encode_datetime, parse_datetime, encode_date, parse_date, \
    encode_time, parse_time, parse_timedelta, encode_timedelta


@dataclass
class Argument(object):
    type: Callable
    many: Union[bool, int] = False
    positional: bool = False
    default: Any = None
    required: bool = False
    constant: bool = False
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
            return obj._namespace[self.name]
        except KeyError:
            return self.default

    def __set__(self, obj, value):
        if self.constant and self.name in obj._namespace:
            return
        obj._namespace[self.name] = self.validate(value)

    def __delete__(self, obj):
        obj._namespace.pop(self.name, None)

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
                raise ValueError(f"argument '{self.name}' is required")
            return None
        if not isinstance(self.many, bool):
            if len(value) != self.many:
                raise ValueError(f"argument '{self.name}' is not of correct length {self.many}")
        if isinstance(value, str) or (self.many is not False and all(isinstance(v, str) for v in value)):
            value = self.decode(value)
        if value is not None and self.valid and not self.valid(value):
            raise ValueError(f"invalid argument for '{self.name}'")
        return value

    def _get_name_or_flag(self, _seen) -> tuple:
        if self.name in _seen:
            raise ValueError(f"argument name '{self.name}' is already in use")
        if not self.positional:
            if self.name[0] in set(a[0] for a in _seen):
                if len(self.name) == 1:
                    raise ValueError(f"'-{self.name[0]}' already exist as a short argument name")
                return '--' + self.name,
            return '-' + self.name[0], '--' + self.name
        return self.name,

    def add_to_parser(self, parser, _seen):
        args = self._get_name_or_flag(_seen)
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
        if self.constant:
            kwargs.update(const=self.constant,
                          nargs='?')
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
        seen = cls._reserved.copy()
        for arg in cls._arguments:
            arg.add_to_parser(cls._arg_parser, seen)
            seen.add(arg.name)
        cls._arg_names = frozenset(seen)
        cls._extend_doc()

    @classmethod
    def _get_arguments(cls):
        arguments = {}
        for c in reversed(cls.__mro__):
            for name, arg in vars(c).items():
                if isinstance(arg, Argument):
                    arguments[arg.name] = arg
        return tuple(arguments.values())

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
        self._namespace = {}
        self._target = target
        if isinstance(args, Mapping):
            if self._fill(**args):
                self._call()
        elif use_app and self._no_arguments(args):
            self._run_app()
        else:
            if self._parse(args):
                self._call()

    def __len__(self) -> int:
        return len(self._namespace)

    def __iter__(self) -> Iterable:
        yield from self._namespace

    def __getitem__(self, key: str):
        return self._namespace[key]

    def _runnable(self):
        return self._is_valid() and self._target

    def _no_arguments(self, args):
        return not args and len(sys.argv) == 1

    def _run_app(self):
        arg_app.ArgApp(parser=self).mainloop()

    def _is_valid(self):
        return all(arg.check_required(self) for arg in self._arguments)

    def _parse(self, args):
        if isinstance(args, str):
            args = [a.strip() for a in args.split()]
        try:
            if args is None and "PYTEST_CURRENT_TEST" in os.environ:
                args = sys.argv[2:]  # fix for running tests with pytest (extra cmd line arg)
            parsed = self._arg_parser.parse_args(args)
        except SystemExit as e:  # intercept when e.g. called with --help
            if e.code not in (None, 0):
                raise
            return False
        else:
            return self._fill(**parsed.__dict__)

    def _fill(self, **kwargs):
        new_kwargs = {arg.name: arg.default for arg in self._arguments}
        new_kwargs.update(self._namespace)
        new_kwargs.update(kwargs)
        self._namespace.clear()
        for name, value in new_kwargs.items():
            if name not in self._arg_names:
                raise AttributeError(f"'{name}' is not a configurable argument")
            setattr(self, name, value)
        return self._runnable()

    def _as_json_dict(self):
        return {arg.name: arg.encode(getattr(self, arg.name)) for arg in self._arguments}

    def _save(self, filename: str, mode: str = 'w'):
        with open(filename, mode) as f:
            f.write(json.dumps(self._as_json_dict()))

    def _call(self, target: Callable = None) -> Any:
        target = target or self._target
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

    def __str__(self) -> str:
        return json.dumps(self._namespace, indent=4)

    def __repr__(self) -> str:
        return json.dumps(self._namespace, indent=4)


if __name__ == '__main__':
    def target(**kwargs):
        print(kwargs)


    class Parser(ArgParser):
        """ this is a test ArgParser """
        a = Argument(int, positional=True, default=3)
        b = Argument(int, valid=lambda v: v < 10)
        c = Argument(int, default=11, constant=True)
        dd = Argument(int, many=3, callback=lambda a, b: print(a, b))


    print(Parser._get_string())
    print('starting')
    parser = Parser('-b 4 -d 1 2 3')
    parser._call(target)
    print('done')
