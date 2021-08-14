import json
import os
import sys
from argparse import ArgumentParser, Action, Namespace
from dataclasses import dataclass
from functools import partial
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

import app


class Missing(object):
    def __bool__(self):
        return False
    def __str__(self):
        return "MISSING"
    __repr__ = __str__


MISSING = Missing()


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

    NO_VALS = (None, "", MISSING)

    def __post_init__(self):
        if self.default not in (None, MISSING):
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
            return obj.namespace[self.name]
        except KeyError:
            if self.default is not MISSING:
                return self.default
            raise AttributeError(f"missing argument '{self.name}'")

    def __set__(self, obj, value):
        if self.constant and self.name in obj.namespace:
            return
        obj.namespace[self.name] = self.validate(value)

    def validate(self, value):
        if value in self.NO_VALS:
            if self.required:
                raise ValueError(f"argument '{self.name}' is required")
        elif value is not None:
            if not isinstance(self.many, bool):
                if len(value) != self.many:
                    raise ValueError(f"argument '{self.name}' is not of correct length {self.many}")
            if self.many is not False:
                value = [self.type(v) for v in value]
            else:
                value = self.type(value)
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

    def parse_key(self, short=False):
        """ return string e.g. '--version', '-v'"""
        if self.positional:
            return ''
        if len(self.args) == 1:
            return self.args[0]
        return self.args[0] if short else self.args[1]

    def parse_value(self, obj):
        value = self.__get__(obj)
        if self.many:
            return ' '.join(str(v) for v in value)
        return str(value)

    def add_to_parser(self, parser, _seen):
        self.args = self._get_name_or_flag(_seen)
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
        if self.callback:
            kwargs.update(action=partial(CallbackAction,
                                         callback=self.callback))
        parser.add_argument(*self.args, **kwargs)


class CallbackAction(Action):
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        self.callback(values, namespace)


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

    @classmethod
    def defaults(cls):
        return {a.name: a.default for a in cls.__arguments__() if a.default is not MISSING}

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

    @classmethod
    def app(cls, target):
        parser = cls(args={}, target=target, _execute=False)
        app.App(parser=parser).mainloop()

    def __init__(self,
                 args: Union[str, Sequence, Mapping, None] = None,
                 target: Callable = None,
                 _execute: bool = True):
        self.target = target
        self.namespace = {}
        if isinstance(args, dict):
            self.update(**args)
        else:
            if isinstance(args, str):
                args = [a.strip() for a in args.split()]
            try:
                parsed = self.parser.parse_args(args)
            except SystemExit as e:  # intercept when e.g. called with --help
                if e.code not in (None, 0):
                    raise
            else:
                self.update(**parsed.__dict__)
        if _execute and self.target:
            self.call()

    def update(self, **kwargs):
        new_kwargs = self.defaults()
        new_kwargs.update(self.namespace)
        new_kwargs.update(kwargs)
        for name, value in new_kwargs.items():
            if name not in self.arg_names:
                raise AttributeError(f"'{name}' is not a configurable argument")
            setattr(self, name, value)

    def __len__(self) -> int:
        return len(self.namespace)

    def __iter__(self) -> Iterable:
        yield from self.namespace

    def __getitem__(self, key: str):
        return self.namespace[key]

    def save(self, filename: str, mode: str = 'w'):
        with open(filename, mode) as f:
            f.write(repr(self))

    def call(self, target: Callable = None) -> Any:
        target = target or self.target
        return target(**self.namespace)

    def command(self, short=False):
        filename = os.path.basename(sys.argv[0])
        key_values = [f"{arg.parse_key(short)} {arg.parse_value(self)}" for arg in self.__arguments__()]
        return filename + ' '.join(key_values)

    def __str__(self) -> str:
        return json.dumps(self.namespace, indent=4)

    def __repr__(self) -> str:
        return json.dumps(self.namespace, indent=4)


if __name__ == '__main__':
    def target(**kwargs):
        print(kwargs)


    class Parser(ArgParser):
        a = Argument(int, positional=True, default=3)
        b = Argument(int, valid=lambda v: v < 10)
        c = Argument(int, default=11, constant=True)
        dd = Argument(int, many=3, callback=lambda a, b: print(a, b))


    print(Parser.string)
    print('starting')
    parser = Parser('-b 4 -d 1 2 3')
    parser.call(target)
    print('done')
