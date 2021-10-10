import json
import os
import sys

from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

from pycicle import arg_gui, cmd_parser
from pycicle.tools import get_stdout, MISSING
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
    callback: Callable[[Any, Mapping], Any] = None
    help: str = ""
    name: Union[str, None] = None  # set in __set_name__

    type_codecs = {
        bool: (encode_bool, parse_bool),
        datetime: (encode_datetime, parse_datetime),
        timedelta: (encode_timedelta, parse_timedelta),
        date: (encode_date, parse_date),
        time: (encode_time, parse_time),
    }

    reserved = {'help'}

    def __post_init__(self):
        """ mainly sets the encoders and decoders for the argument """
        encode, decode = self.type_codecs.get(self.type, (None, None))
        self._encode = encode or str  # str is default
        self._decode = decode or self.type  # self.type is default (int('3') == 3)
        self.flags = None  # set in ArgParser.__init_subclass__

    def __set_name__(self, cls, name):
        """ descriptor method to set the name to the attribute name in the owner class """
        self.name = name

    def __get__(self, obj, cls=None):
        """ see python descriptor docs for the magic """
        if obj is None:
            return self
        try:
            return obj.__dict__[self.name]
        except KeyError:
            return self.default

    def __set__(self, obj, value):
        """ see python descriptor docs for the magic """
        if self.callback:
            self.callback(value, obj)
        obj.__dict__[self.name] = self.validate(value)

    def __delete__(self, obj):
        """ see python descriptor docs for the magic """
        obj.__dict__.pop(self.name, None)

    def check_config(self):
        """
        Called in __init_subclass__ of owner class because self.name must be set to give clearer error messages and
        python __set_name__ changes all exceptions to (somewhat vague) RuntimeError.
        """
        if self.name.startswith('_'):
            raise ConfigError(f"Argument name '{self.name}' cannot start with an '_' to prevent name conflicts")
        self.default = self.validate(self.default, _config=True)
        if self.novalue is not MISSING:
            if self.positional:
                raise ConfigError(f"Argument '{self.name}' is flag only and cannot be positional")
            self.novalue = self.validate(self.novalue, _config=True)

    def encode(self, value):
        """ creates str version of value, takes 'many' into account """
        if value is None:
            return ''
        if self.many:
            return [self._encode(v) for v in value]
        return self._encode(value)

    def decode(self, value):
        """ creates value from str, takes 'many' into account """
        if self.type is not str and value == '':
            return None
        if self.many:
            return [self._decode(v) for v in value]
        return self._decode(value)

    def encoded(self, obj):
        """ convenience, applies encode to object """
        return self.encode(self.__get__(obj))

    def decoded(self, dct):
        """ convenience, applies decode to dict, e.g. for init from json """
        return self.decode(dct[self.name])

    def validate(self, value, _config=False):
        """ performs validation and decoding of argument values """
        exception_class = ConfigError if _config else ValueError
        if value is None or value is MISSING:
            if not _config and self.required:
                raise ValueError(f"Argument value '{self.name}' is required")
            return value
        if self.many is not False:
            if not isinstance(value, (list, tuple)):
                raise exception_class(f"Argument value for '{self.name}' is not a list or tuple")
            value = list(value)
        if not isinstance(self.many, bool):
            if len(value) != self.many:
                raise exception_class(f"Argument value for '{self.name}' is not of length {self.many}")
        try:
            if isinstance(value, str) or (self.many is not False and all(isinstance(v, str) for v in value)):
                value = self.decode(value)
            if value is not None and self.valid and not self.valid(value):
                raise exception_class(f"Invalid value: {str(value)} for argument '{self.name}'")
        except TypeError as e:
            raise exception_class(str(e))
        return value

    def _get_flag_s(self, seen) -> tuple:
        """ internal: creates flags for argument (e.g. -f, --file), no flag if positional """
        if self.name in self.reserved:
            raise ConfigError(f"Argument name '{self.name}' is reserved")

        if self.positional:
            if not all(arg.positional for arg in seen.values()):
                raise ConfigError(f"Cannot place positional argument '{self.name}' after non-positional arguments")
            if any(arg.many is True for arg in seen.values()):
                raise ConfigError(f"Cannot place positional argument '{self.name}' after non-positional arguments")
            return ()
        else:
            seen_shorts = set(a[0] for a in seen) | set(a[0] for a in self.reserved)
            if self.name[0] in seen_shorts:
                if len(self.name) == 1:
                    raise ConfigError(f"'-{self.name[0]}' already exist as a short argument name")
                return '--' + self.name,
            return '--' + self.name, '-' + self.name[0]

    def finalize(self, seen):
        """ adds argument to argparse parser, converts options """
        self.flags = self._get_flag_s(seen)

    def _cmd_flag(self, short=False):
        """ return flag e.g. '--version', '-v' if short"""
        if len(self.flags) == 0:  # ~ positional is True
            return ''
        if len(self.flags) == 1:
            return self.flags[0]
        return self.flags[1] if short else self.flags[0]

    def _cmd_value(self, value):
        """ creates command line version of value """
        if self.many:
            return ' '.join(self.encode(value))
        return self.encode(value)

    def cmd(self, obj, short=False):
        """ creates command line part for this argument """
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
        """ creates json version of argument value """
        value = self.__get__(obj)
        if value is None:
            return None
        return self.encode(value)

    def check_required(self, obj):
        """ raises exception if argument is required and no value is present """
        value = self.__get__(obj)
        if self.required and value is None and self.default is not None:
            raise ValueError(f"missing required argument '{self.name}'")


class ArgParser(Mapping):
    """
    This class uses the arguments to parse and run the command line or start the GUI. A few notes:
     - The class itself stores the values for all the arguments. It subclasses Mapping and can be used
     as keyword arguments for a function (e.g. func(**parser)),
     - To enable this usage, all methods, class and other attributes start with an underscore,
     - It partially uses the standard library argparse to run from the command line
            (TODO: remove this dependency?)
     - the parser can call a target callable: if parser = ArgParser(): parser(func)

    """
    _arguments = None  # set in __init_subclass__

    def __init_subclass__(cls, **kwargs):
        """ mainly initialises the argparse.ArgumentParser and adds arguments to the parser """
        super().__init_subclass__(**kwargs)
        cls._arguments = tuple(cls._get_arguments())
        seen = {}  # to prevent repeated short flags
        for arg in cls._arguments:
            arg.finalize(seen)
            seen[arg.name] = arg

    @classmethod
    def _get_arguments(cls):
        """ gathers and validates the Argument descriptors """
        arguments = {}  # dict to let subclasses override arguments
        for c in reversed(cls.__mro__):
            for name, arg in vars(c).items():
                if isinstance(arg, Argument):
                    arg.check_config()  # see comment in 'check_config'
                    arguments[arg.name] = arg  # override if already present
        return arguments.values()

    @classmethod
    def _cmd_help(cls):
        """ used by GUI to show help generated by argparse """
        return ''  # TODO: implement

    @classmethod
    def _load(cls, filename: str, mode: str = 'r'):
        """ used by GUI to load argument values from file """
        with open(filename, mode) as f:
            json_dict = json.load(f)
        return cls({arg.name: arg.decoded(json_dict) for arg in cls._arguments})

    def __init__(self,
                 args: Union[str, Sequence, Mapping, None] = None,
                 target: Callable = None,  # target callable
                 run_gui: bool = False):  # False prevents GUI from starting
        if run_gui:
            self._run_gui(target)
        else:
            self._parse(args)
            if target:
                self(target)  # uses the __call__ method

    def __len__(self) -> int:
        """ return number of arguments """
        return len(self.__dict__)

    def __iter__(self) -> Iterable:
        """ iterates over argument names """
        yield from self.__dict__

    def __getitem__(self, name: str):
        """ returns value for argument 'name'"""
        return self.__dict__[name]

    def _run_gui(self, target):
        """ starts the GUI """
        arg_gui.ArgGui(parser=self, target=target).mainloop()

    def _parse(self, args):
        if args is None:
            if "PYTEST_CURRENT_TEST" in os.environ:
                args = sys.argv[2:]  # fix for running tests with pytest
            else:
                args = sys.argv[1:]
        elif isinstance(args, Mapping):
            self._update(args)
            args = self._command()

        if isinstance(args, str):
            args = [s.strip() for s in args.split()]

        if '-h' in args or '--help' in args:
            print(self._cmd_help())
        else:
            parsed = cmd_parser.parse(args, arguments=self._arguments)
            self._update(parsed)

    def _update(self, kwargs):
        """ refills self.__dict__ with validated values """
        new_kwargs = {arg.name: arg.default for arg in self._arguments}
        new_kwargs.update(self.__dict__)
        new_kwargs.update(kwargs)
        self.__dict__.clear()
        for name, value in new_kwargs.items():
            setattr(self, name, value)

    def _command(self, short=False, prog=False):
        """ creates the command line that can be used to call the parser:
            - short: short flags (e.g. -d),
            - prog: called file from command line is included"""
        cmds = [arg.cmd(self, short) for arg in self._arguments]
        arg_string = ' '.join(cmd for cmd in cmds if cmd)
        if prog:
            return f"{os.path.basename(sys.argv[0])} {arg_string}"
        return arg_string

    def __call__(self, target: Callable) -> Any:
        """ calls the target with the argument values """
        if target is None:
            raise ValueError(f"cannot call missing target")
        for arg in self._arguments:
            arg.check_required(self)
        self._parse(self._command())  # runs through the validation once again
        return target(**self)  # call the target

    def _save(self, filename: str, mode: str = 'w'):
        """ saves arguments as json to a file """
        json_dict = {arg.name: arg.encoded(self) for arg in self._arguments}
        with open(filename, mode) as f:
            f.write(json.dumps(json_dict))


if __name__ == '__main__':
    pass
