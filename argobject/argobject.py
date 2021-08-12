import json
from argparse import ArgumentParser
from collections import namedtuple
from dataclasses import dataclass
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

from library.tools import MISSING


@dataclass
class Argument(object):
    type: Callable
    many: Union[bool, int] = False
    positional: bool = False
    required: bool = False
    constant: bool = False
    default: Any = MISSING
    valid: Callable = None
    help: str = ""
    name: Union[str, None] = None  # set in __set_name__

    def __post_init__(self):
        if self.default is not MISSING:
            if isinstance(self.type, type):
                if not isinstance(self.default, self.type):
                    raise TypeError(f"default '{self.default}' is not of type '{self.type.__name__}'")
            if self.valid and not self.valid(self.default):
                raise ValueError(f"invalid default '{self.default}'")

    def __set_name__(self, cls, name):
        self.name = name

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        try:
            obj.arguments[self.name]
        except KeyError:
            if self.default is not MISSING:
                return self.default
            raise AttributeError(f"missing argument '{self.name}'")

    def __set__(self, obj, value):
        if value is not None:
            if self.many is not False:
                value = [self.type(v) for v in value]
            else:
                value = self.type(value)
        if self.valid and not self.valid(value):
            raise ValueError(f"invalid argument for '{self.name}'")
        if self.constant and self.name in obj.arguments:
            raise AttributeError(f"constant Argument '{self.name}' is already set")
        obj.arguments[self.name] = value

    def _get_name_or_flag(self, _seen) -> tuple:
        if not self.positional:
            if self.name[0] in set(a[0] for a in _seen):
                if len(self.name) == 1:
                    raise ValueError(f"'{self.name}' already exist as a short argument name")
                return '--' + self.name,
            return '--' + self.name, '-' + self.name[0]
        return self.name,

    def add_to_parser(self, parser, _seen):
        args = self._get_name_or_flag(_seen)
        kwargs = dict(type=self.type,
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
        parser.add_argument(*args, **kwargs)


class ArgParser(Mapping):
    parser_class = ArgumentParser
    arg_names = None  # set in __init_subclass__

    @classmethod
    def __arguments__(cls) -> Iterable:
        for c in cls.__mro__:
            for name, arg in vars(c).items():
                if isinstance(arg, Argument):
                    yield arg

    @classmethod
    @property
    def string(cls):
        line_end = '\n\t'
        return f"{cls.__name__}({','.join(c.__name__ for c in cls.__bases__)}):" \
               f"{line_end}{line_end.join(map(str, cls.__arguments__()))}"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.parser = cls.parser_class(**kwargs)
        seen_arg_names = set()
        for arg in cls.__arguments__():
            arg.add_to_parser(cls.parser, _seen=seen_arg_names)
            seen_arg_names.add(arg.name)
        cls.arg_names = seen_arg_names

    @classmethod
    def load(cls, filename: str, mode: str = 'r'):
        with open(filename, mode) as f:
            return cls(json.load(f))

    def __init__(self, args: Union[str, Sequence, Mapping, None] = None):
        self.arguments = {}
        if isinstance(args, dict):
            kwargs = args
        else:
            if isinstance(args, str):
                args = [a.strip() for a in args.split()]
            parsed = self.parser.parse_args(args)
            kwargs = parsed.__dict__
        for name, value in kwargs.items():
            setattr(self, name, value)

    def __len__(self) -> int:
        return len(self.arguments)

    def __iter__(self) -> Iterable:
        yield from self.arguments

    def __getitem__(self, key: str):
        return self.arguments[key]

    def save(self, filename: str, mode: str = 'w'):
        with open(filename, mode) as f:
            f.write(repr(self))

    def call(self, target: Callable) -> Any:
        return target(**self.arguments)

    def __str__(self) -> str:
        return json.dumps(self.arguments, indent=4)

    def __repr__(self) -> str:
        return json.dumps(self.arguments, indent=4)


if __name__ == '__main__':
    def target(**kwargs):
        print(kwargs)


    class Parser(ArgParser):
        a = Argument(int, positional=True, default=3)
        b = Argument(int, valid=lambda v: v < 10)
        c = Argument(int, default=11, constant=True)
        dd = Argument(int, many=3)

    print(Parser.string)
    print('starting')
    parser = Parser('-b 2 --dd 1 2 3')
    parser.call(target)
    print('done')


    namedtuple
