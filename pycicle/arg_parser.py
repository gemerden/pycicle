import json
import os
import sys

from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

from pycicle import arg_gui
from pycicle.tools import MISSING, DEFAULT
from pycicle.parsers import parse_bool, encode_bool, encode_datetime, parse_datetime, encode_date, parse_date, \
    encode_time, parse_time, parse_timedelta, encode_timedelta


class ConfigError(ValueError):
    pass


@dataclass
class Argument(object):
    type: Callable
    many: bool = False
    default: Any = MISSING
    missing: Any = MISSING
    valid: Callable[[Any], bool] = None
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

    @property
    def required(self):
        return self.default is MISSING

    def __set_name__(self, cls, name):
        """ descriptor method to set the name to the attribute name in the owner class """
        self.name = name
        self.flags = ('--' + name, '-' + name[0])

    def __get__(self, obj, cls=None):
        """ see python descriptor docs for the magic """
        if obj is None:
            return self
        try:
            return obj.__dict__[self.name]
        except KeyError:
            return self.default  # can be MISSING

    def __set__(self, obj, value):
        """ see python descriptor documentation for the magic """
        obj.__dict__[self.name] = self.validate(value)

    def __delete__(self, obj):
        """ see python descriptor documentation for the magic """
        obj.__dict__.pop(self.name, None)

    def check_config(self, existing):
        """
        Called in __init_subclass__ of owner class because self.name must be set to give clearer error messages and
        python __set_name__ changes all exceptions to (somewhat vague) RuntimeError.
        """
        if self.name in self.reserved:
            raise ConfigError(f"Argument name '{self.name}' is reserved")
        if self.name.startswith('_'):
            raise ConfigError(f"Argument name '{self.name}' cannot start with an '_' (to prevent name conflicts)")

        if self.default is not MISSING:
            self.default = self.validate(self.default, _config=True)
        if self.missing is not MISSING:
            if self.default is MISSING:
                raise ConfigError(f"if 'missing' is defined, a default must also be defined in '{self.name}'")
            self.missing = self.validate(self.missing, _config=True)

        existing_short_flags = set(a[0] for a in existing) | set(a[0] for a in self.reserved)
        if self.flags[-1] in existing_short_flags:
            self.flags = self.flags[:-1]  # remove short flag

    def encode(self, value):
        """ creates str version of value, takes 'many' into account """
        if value is None or value is MISSING:
            return ''
        if self.many:
            return [self._encode(v) for v in value]
        return self._encode(value)

    def decode(self, value):
        """ creates value from str, takes 'many' into account """
        if self.type is not str and value == '':
            return self.default
        if self.many:
            return [self._decode(v) for v in value]
        return self._decode(value)

    def parse(self, value):
        if self.missing is not MISSING and value is MISSING:
            return self.missing
        if value is MISSING or value is DEFAULT:
            if self.default is MISSING:
                raise ValueError(f"missing value for '{self.name}'")
            return self.default
        return self.decode(value)

    def validate(self, value, _config=False):
        """ performs validation and decoding of argument values """
        exception_class = ConfigError if _config else ValueError
        if value is MISSING:
            if not _config and self.default is MISSING:
                raise ValueError(f"Argument value '{self.name}' is required")
            return value
        if _config and value is None:
            return None
        if value is self.default is None:
            return None
        if self.many:
            if not isinstance(value, Sequence):
                raise exception_class(f"Argument value for '{self.name}' is not a list or tuple")
            value = list(value)
        try:
            if isinstance(value, str) or (self.many and all(isinstance(v, str) for v in value)):
                value = self.decode(value)
            if self.valid and not self.valid(value):
                raise exception_class(f"Invalid value: {str(value)} for argument '{self.name}'")
        except TypeError as e:
            raise exception_class(str(e))
        return value

    def _cmd_flag(self, short=False):
        """ return flag e.g. '--version', '-v' if short"""
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
        if self.missing is not MISSING:
            if value == self.missing:
                return self._cmd_flag(short)
            return ''  # value will be the default
        cmd_value = self._cmd_value(value)
        if cmd_value == '':
            return ''
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
    _flag_lookup = None  # set in __init_subclass__

    def __init_subclass__(cls, **kwargs):
        """ mainly initialises the argparse.ArgumentParser and adds arguments to the parser """
        super().__init_subclass__(**kwargs)
        cls._arguments = cls._get_arguments()
        cls._flag_lookup = cls._create_flag_lookup()

    @classmethod
    def _get_arguments(cls):
        """ gathers and validates the Argument descriptors """
        arguments = {}  # dict to let subclasses override arguments
        for c in reversed(cls.__mro__):
            for name, arg in vars(c).items():
                if isinstance(arg, Argument):
                    arg.check_config(arguments)  # see comment in 'check_config'
                    arguments[arg.name] = arg  # overrides if already present
        return arguments

    @classmethod
    def _create_flag_lookup(cls):
        flag_lookup = {}
        for argument in cls._arguments.values():
            for flag in argument.flags:
                flag_lookup[flag] = argument
        return flag_lookup

    @classmethod
    def _parse(cls, cmd_line):
        arg_defs = cls._arguments
        flag_lookup = cls._flag_lookup

        if isinstance(cmd_line, str):
            cmd_line = [s.strip() for s in cmd_line.split()]

        def get_args_kwargs(cmd_line):
            kwargs = {None: []}  # None key for positional arguments
            current_name = None
            for flag_or_value in cmd_line:
                if flag_or_value in flag_lookup:  # flagged
                    current_name = flag_lookup[flag_or_value].name
                    kwargs[current_name] = MISSING
                elif current_name is not None:  # not flagged
                    if arg_defs[current_name].many:
                        if kwargs[current_name] is MISSING:
                            kwargs[current_name] = []
                        kwargs[current_name].append(flag_or_value)
                    else:
                        kwargs[current_name] = flag_or_value
                else:  # positional argument
                    kwargs[None].append(flag_or_value)
            args = kwargs.pop(None)
            return args, kwargs

        args, kwargs = get_args_kwargs(cmd_line)

        pos_arg_defs = [a for n, a in arg_defs.items() if n not in kwargs]
        try:  # note: if args are empty, index error cannot occur
            while len(args) and not pos_arg_defs[0].many:
                kwargs[pos_arg_defs.pop(0).name] = args.pop(0)
            while len(args) and not pos_arg_defs[-1].many:
                kwargs[pos_arg_defs.pop(-1).name] = args.pop(-1)
        except IndexError:
            raise ValueError("too many positional arguments found")

        if len(args) and len(pos_arg_defs) == 1:
            kwargs[pos_arg_defs[0].name] = args

        return {n: arg.parse(kwargs.get(n, DEFAULT)) for n, arg in arg_defs.items()}

    @classmethod
    def _cmd_help(cls):
        """ used by GUI to show help generated by argparse """
        return ''  # TODO: implement

    @classmethod
    def _load(cls, filename: str, mode: str = 'r'):
        """ used by GUI to load argument values from file """
        with open(filename, mode) as f:
            json_dict = json.load(f)
        return cls({name: arg.decode(json_dict[name]) for name, arg in cls._arguments.items()})

    def __init__(self,
                 args: Union[str, Sequence, Mapping, None] = None,  # representation of command line arguments
                 target: Callable = None,  # target callable
                 run_gui: bool = False):   # if True: start the parser as a GUI
        if run_gui:
            self._run_gui(target)
        else:
            self._parse_args(args)
            if target:
                self(target)  # uses the __call__ method

    def __len__(self) -> int:
        """ return number of arguments """
        return len(self._arguments)

    def __iter__(self) -> Iterable:
        """ iterates over argument names """
        yield from self._arguments

    def __getitem__(self, name: str):
        """ returns value for argument 'name'"""
        return self.__dict__[name]

    def _run_gui(self, target):
        """ starts the GUI """
        arg_gui.ArgGui(parser=self, target=target).mainloop()

    def _parse_args(self, args):
        if args is None:
            if "PYTEST_CURRENT_TEST" in os.environ:
                args = sys.argv[1:]  # fix for running tests with pytest
            else:
                args = sys.argv
        elif isinstance(args, Mapping):
            self._update(args)
            args = self._command()

        if isinstance(args, str):
            args = [s.strip() for s in args.split()]

        if '-h' in args or '--help' in args:
            print(self._cmd_help())
        else:
            parsed = self._parse(args)
            self._update(parsed)

    def _update(self, kwargs):
        """ refills self.__dict__ with validated values """
        new_kwargs = {name: arg.default for name, arg in self._arguments.items()}
        new_kwargs.update(self.__dict__)
        new_kwargs.update(kwargs)
        self.__dict__.clear()
        for name, value in new_kwargs.items():
            setattr(self, name, value)

    def _command(self, short=False, prog=False):
        """ creates the command line that can be used to call the parser:
            - short: short flags (e.g. -d),
            - prog: called file from command line is included"""
        cmds = [arg.cmd(self, short) for arg in self._arguments.values()]
        arg_string = ' '.join(cmd for cmd in cmds if cmd)
        if prog:
            return f"{os.path.basename(sys.argv[0])} {arg_string}"
        return arg_string

    def __call__(self, target: Callable) -> Any:
        """ calls the target with the argument values """
        if target is None:
            raise ValueError(f"cannot call missing target")
        for arg in self._arguments.values():
            arg.check_required(self)
        self._parse(self._command())  # runs through the validation once again
        return target(**self)  # call the target

    def _save(self, filename: str, mode: str = 'w'):
        """ saves arguments as json to a file """
        json_dict = {name: arg.encode(getattr(self, name)) for name, arg in self._arguments.items()}
        with open(filename, mode) as f:
            f.write(json.dumps(json_dict))


if __name__ == '__main__':
    pass
