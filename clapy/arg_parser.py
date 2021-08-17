import json
import sys
from argparse import ArgumentParser, Action, Namespace
from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from functools import partial
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

from clapy import arg_app
from tools import get_stdout, Codec, MISSING, from_none, into_none
from parsers import parse_bool, encode_bool, encode_datetime, parse_datetime, encode_date, parse_date, encode_time, parse_time, \
    parse_timedelta, encode_timedelta


@dataclass
class Argument(object):
    type: Callable
    many: Union[bool, int] = False
    positional: bool = False
    required: bool = False
    constant: bool = False
    default: Any = MISSING
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

    template = "{name} {args}: \t\t\t{type}, many={many}, default={default}, required={required}, constant={constant}"

    def __post_init__(self):
        encode, decode = self.type_codecs.get(self.type, (None, None))
        self.encode = from_none(encode or str)
        self.decode = into_none(decode or self.type)

    def __set_name__(self, cls, name):
        self.name = name
        self._validate_default()

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        try:
            return obj._namespace[self.name]
        except KeyError:
            if self.default is not MISSING:
                return self.default
            raise AttributeError(f"missing argument '{self.name}'")

    def __set__(self, obj, value):
        if self.constant and self.name in obj._namespace:
            return
        obj._namespace[self.name] = self.validate(value)

    def __delete__(self, obj):
        obj._namespace.pop(self.name, None)

    def _validate_default(self):
        if self.default is MISSING:
            if self.constant:
                raise ValueError(f"constant argument '{self.name}' must have a default")
        else:
            self.default = self.validate(self.default)

    def validate(self, value):
        if value in (None, ""):
            if self.required:
                raise ValueError(f"argument '{self.name}' is required")
            return None
        if not isinstance(self.many, bool):
            if len(value) != self.many:
                raise ValueError(f"argument '{self.name}' is not of correct length {self.many}")
        if self.many is not False:
            if all(isinstance(v, str) for v in value):
                value = [self.decode(v) for v in value]
        elif isinstance(value, str):
            value = self.decode(value)
        if self.valid and not self.valid(value):
            raise ValueError(f"invalid argument for '{self.name}'")
        return value

    def _get_name_or_flag(self, _seen) -> tuple:
        if not self.positional:
            if self.name[0] in set(a[0] for a in _seen):
                if len(self.name) == 1:
                    raise ValueError(f"'{self.name}' already exist as a short argument name")
                return '--' + self.name,
            return '-' + self.name[0], '--' + self.name
        return self.name,

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
            return ' '.join(self.encode(v) for v in value)
        return self.encode(value)

    def add_to_parser(self, parser, _seen):
        args = self._get_name_or_flag(_seen)
        kwargs = dict(type=self.decode,
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
        if self.default is not MISSING:
            kwargs.update(default=self.default)
        if self.constant:
            kwargs.update(const=self.constant,
                          nargs='?')
        if self.callback:
            kwargs.update(action=partial(CallbackAction,
                                         callback=self.callback))
        self.args = () if self.positional else args
        parser.add_argument(*args, **kwargs)

    def __str__(self):
        def get_name(arg):
            try:
                return arg.__name__
            except AttributeError:
                return str(arg)

        return self.template.format(**{n: get_name(v) for n, v in self.__dict__.items()})


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
        seen = set()
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
    def _defaults(cls):
        return {arg.name: arg.default for arg in cls._arguments if arg.default is not MISSING}

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
    def _load(cls, filename: str, mode: str = 'r'):
        with open(filename, mode) as f:
            json_dict = json.load(f)
        return cls({n: getattr(cls, n).decode(js) for n, js in json_dict.items()})

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

    def _runnable(self):
        return self._is_valid() and self._target

    def _no_arguments(self, args):
        return not args and len(sys.argv) == 1

    def _run_app(self):
        arg_app.App(parser=self).mainloop()

    def _is_valid(self):
        for arg in self._arguments:
            if arg.required and arg.name not in self:
                return False
        return True

    def _parse(self, args):
        if isinstance(args, str):
            args = [a.strip() for a in args.split()]
        try:
            parsed = self._arg_parser.parse_args(args)
        except SystemExit as e:  # intercept when e.g. called with --help
            if e.code not in (None, 0):
                raise
            return False
        else:
            return self._fill(**parsed.__dict__)

    def _fill(self, **kwargs):
        new_kwargs = self._defaults()
        new_kwargs.update(self._namespace)
        new_kwargs.update(kwargs)
        self._namespace.clear()
        for name, value in new_kwargs.items():
            if name not in self._arg_names:
                raise AttributeError(f"'{name}' is not a configurable argument")
            setattr(self, name, value)
        return self._runnable()

    def __len__(self) -> int:
        return len(self._namespace)

    def __iter__(self) -> Iterable:
        yield from self._namespace

    def __getitem__(self, key: str):
        return self._namespace[key]

    def _asdict(self):
        result = {}
        for arg in self._arguments:
            value = getattr(self, arg.name, MISSING)
            if value is not MISSING:
                result[arg.name] = value
        return result

    def _save(self, filename: str, mode: str = 'w'):
        json_dict = {n: getattr(self.__class__, n).encode(a) for n, a in self._asdict().items()}
        with open(filename, mode) as f:
            f.write(json.dumps(json_dict))

    def _call(self, target: Callable = None) -> Any:
        target = target or self._target
        return target(**self)

    def _command(self, short=False):
        items = []
        for arg in self._arguments:
            cmd_key, cmd_value = arg.cmd_key(short), arg.cmd_value(self)
            if cmd_value:
                items.append(f"{cmd_key} {cmd_value}")
        return ' '.join(items).strip()

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
