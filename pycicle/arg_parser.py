import os
import sys

from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from typing import Mapping, Callable, Union, Any, Sequence, Iterable

from pycicle import arg_gui
from pycicle.tools import MISSING, DEFAULT, get_entry_file
from pycicle.parsers import parse_bool, encode_bool, encode_datetime, parse_datetime, encode_date, parse_date, \
    encode_time, parse_time, parse_timedelta, encode_timedelta


class ConfigError(ValueError):
    pass


class MissingError(ValueError):
    pass


@dataclass
class Argument(object):
    type: Callable
    many: bool = False
    default: Any = MISSING
    valid: Callable[[Any], bool] = None
    help: str = ""
    name: str = ""  # set in __set_name__

    type_codecs = {
        bool: (encode_bool, parse_bool),
        datetime: (encode_datetime, parse_datetime),
        timedelta: (encode_timedelta, parse_timedelta),
        date: (encode_date, parse_date),
        time: (encode_time, parse_time),
    }

    reserved = {'help', 'gui'}

    def __post_init__(self):
        """ mainly sets the encoders and decoders for the argument """
        encode, decode = self.type_codecs.get(self.type, (None, None))
        self._encode = encode or str  # str is default
        self._decode = decode or self.type  # self.type is default (int('3') == 3)
        self.flags = None  # set in ArgParser.__init_subclass__

    @property
    def full_name(self):
        return f"{self.cls.__name__}.{self.name}"

    @property
    def required(self):
        return self.default is MISSING

    def is_switch(self):
        return self.type is bool and self.default is False  # so self.many must also be False

    def is_encoded(self, value):
        if value is MISSING or value is DEFAULT:
            return True
        if self.type is str:
            if isinstance(value, str):
                return False
            raise ValueError(f"non-string value '{value}' for string attribute '{self.name}'")
        else:
            return isinstance(value, str)

    def __set_name__(self, cls, name):
        """ descriptor method to set the name to the attribute name in the owner class """
        self.cls = cls
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
        if self.is_encoded(value):
            value = self.parse(value)
        obj.__dict__[self.name] = self.validate(value)

    def __delete__(self, obj):
        """ see python descriptor documentation for the magic """
        obj.__dict__.pop(self.name, None)

    def validate_config(self, existing):
        """
        Called in __init_subclass__ of owner class because self.name must be set to give clearer error messages and
        python __set_name__ changes all exceptions to (somewhat vague) RuntimeError.
        """
        if self.name in self.reserved:
            raise ConfigError(f"Argument name '{self.name}' is reserved")

        if self.name.startswith('_'):
            raise ConfigError(f"Argument name '{self.name}' cannot start with an '_' (to prevent name conflicts)")

        self.default = self._validate_default(self.default)

        if any(self.flags[-1] == e[0] for e in existing):
            self.flags = self.flags[:-1]  # remove short flag

    def encode(self, value):
        """ creates str version of value, takes 'many' into account """
        if value is None or value is MISSING:
            return ''
        if self.many:
            return [self._encode(v) for v in value]
        return self._encode(value)

    def decode(self, string):
        """ creates value from str, takes 'many' into account """
        if self.type is not str and string == '':
            return self.default
        if self.many:
            return [self._decode(v) for v in string.split()]
        return self._decode(string)

    def parse(self, value):
        if value is MISSING:  # but flag was there
            if self.is_switch():
                return True
            raise MissingError(f"missing value for '{self.name}'")
        if value is DEFAULT:  # flag was not there
            if self.default is MISSING:
                raise MissingError(f"missing value for '{self.name}'")
            return self.default
        return self.decode(value)

    def cast(self, value):
        return value if type(value) is self.type else self.type(value)

    def _validate(self, value):
        if self.many:
            value = list(map(self.cast, value))
        else:
            value = self.cast(value)

        if self.valid and not self.valid(value):
            raise ValueError(f"Invalid value: {str(value)} for argument '{self.name}'")
        return value

    def validate(self, value):
        """ performs validation and decoding of argument values """
        if value is self.default is None:
            return None
        try:
            return self._validate(value)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError(f"error in '{self.name}' for value '{value}': " + str(error))

    def _validate_default(self, value):
        if value is None or value is MISSING:
            return value
        try:
            return self._validate(value)
        except (TypeError, ValueError, AttributeError) as error:
            raise ConfigError(f"error in '{self.full_name}' for default '{value}': " + str(error))

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
        if self.is_switch():
            if value:
                return self._cmd_flag(short)
            return ''
        cmd_value = self._cmd_value(value)
        if cmd_value == '':
            return ''
        return f"{self._cmd_flag(short)} {cmd_value}"


class Kwargs(object):
    """
    This class uses the arguments to parse and run the command line or start the GUI. A few notes:
     - The class itself stores the values for all the arguments,
     - To enable this usage, all methods, class and other attributes start with an underscore,
    """
    _arguments = None  # set in __init_subclass__

    def __init_subclass__(cls, **kwargs):
        """ mainly initialises the argparse.ArgumentParser and adds arguments to the parser """
        super().__init_subclass__(**kwargs)
        cls._arguments = {n: a for n, a in vars(cls).items() if isinstance(a, Argument)}

    @classmethod
    def _parse(cls, cmd_line):
        arg_defs = cls._arguments
        flag_lookup = {f: a for a in arg_defs.values() for f in a.flags}

        def reunite(kwarg_lists):
            return {n: ' '.join(lst) if lst is not MISSING else lst for n, lst in kwarg_lists.items()}

        def get_args_kwargs(cmd_line_list):
            """ gets args and kwargs in encoded (str) form """
            kwargs = {None: []}  # None key for positional arguments
            current_name = None  # positionals come first on cmd line
            for flag_or_value in cmd_line_list:
                if flag_or_value in flag_lookup:  # flag found
                    current_name = flag_lookup[flag_or_value].name
                    kwargs[current_name] = MISSING  # stays if no values are found
                elif current_name is not None:  # value after flag
                    if kwargs[current_name] is MISSING:
                        kwargs[current_name] = []  # replace MISSING
                    kwargs[current_name].append(flag_or_value)
                else:  # positional argument before any flags
                    kwargs[None].append(flag_or_value)
            return kwargs.pop(None), kwargs  # args, kwargs

        def get_pos_kwargs(pos_args):
            """ assigns positional string values to arguments """
            pos_arg_defs = []
            for name, arg_def in arg_defs.items():
                if name in kwargs:
                    break  # break on first key already present
                pos_arg_defs.append(arg_def)

            pos_kwargs = {}
            try:  # note: if len(args) == 0, index error cannot occur
                while len(pos_args) and not pos_arg_defs[0].many:  # from left
                    pos_kwargs[pos_arg_defs.pop(0).name] = pos_args.pop(0)
                while len(pos_args) and not pos_arg_defs[-1].many:  # from right
                    pos_kwargs[pos_arg_defs.pop(-1).name] = pos_args.pop(-1)
            except IndexError:
                raise ValueError("too many positional arguments found")

            if len(pos_args) and len(pos_arg_defs) == 1:  # remaining
                pos_kwargs[pos_arg_defs[0].name] = pos_args
            return pos_kwargs

        if isinstance(cmd_line, str):
            cmd_line = cmd_line.split()

        args, kwargs = get_args_kwargs(cmd_line)
        kwargs.update(get_pos_kwargs(args))
        kwargs = reunite(kwargs)
        return {n: a.parse(kwargs.get(n, DEFAULT)) for n, a in arg_defs.items()}

    def __init__(self, *cmd_line: str):
        super().__init__()
        if cmd_line:
            self._update(self._parse(' '.join(cmd_line)))
        else:
            self._update(self._defaults())

    def _defaults(self):
        return {n: a.default for n, a in self._arguments.items() if a.default is not MISSING}

    def _update(self, kwargs):
        """ fills self with values """
        for name, value in kwargs.items():
            setattr(self, name, value)

    def _as_dict(self):
        return self.__dict__.copy()

    def __call__(self, target: Callable) -> Any:
        """ calls the target with the argument values """
        if target is None:
            raise ValueError(f"cannot call missing target")
        self._parse(self._command())  # runs through the validation once again
        return target(**self.__dict__)  # call the target

    def _command(self, short=False, prog=False, path=True):
        """ creates the command line that can be used to call the parser:
            - short: short flags (e.g. -d) if possible,
            - prog: called file from command line is included"""
        cmds = [arg.cmd(self, short) for arg in self._arguments.values()]
        cmd_line = ' '.join(cmd for cmd in cmds if cmd)
        if prog:
            return f"{get_entry_file(path)} {cmd_line}"
        return cmd_line


class ArgParser(object):
    """
    This class uses the arguments to parse and run the command line or start the GUI. A few notes:
     - The class itself stores the values for all the arguments. It subclasses Mapping and can be used
     as keyword arguments for a function (e.g. func(**parser)),
     - To enable this usage, all methods, class and other attributes start with an underscore,
     - the parser can call a target callable: if parser = ArgParser(): parser(func)

    """
    kwargs_class = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        cls.kwargs_class = cls._create_kwargs_class()
        cls.arguments = cls.kwargs_class._arguments

    @classmethod
    def _create_kwargs_class(cls):
        """ gathers and validates the Argument descriptors """
        arguments = {}  # dict to let subclasses override arguments
        for c in reversed(cls.__mro__):
            for name, arg in vars(c).items():
                if isinstance(arg, Argument):
                    arguments.pop(arg.name, None)
                    arg.validate_config(arguments)  # see comment in 'validate_config'
                    arguments[arg.name] = arg  # overrides if already present
        return type(cls.__name__ + 'Kwargs', (Kwargs,), arguments)

    @classmethod
    def cmd_line_help(cls):
        """ used by GUI to show help generated by argparse """
        return ''  # TODO: implement

    @classmethod
    def load(cls, filename: str, mode: str = 'r'):
        """ used by GUI to load command line from file """
        with open(filename, mode) as f:
            cmd_line = f.read()
        return cls(cmd_line)

    @classmethod
    def _valid_cmd_line(cls, cmd_line):
        if cmd_line is None:
            if "PYTEST_CURRENT_TEST" in os.environ:
                cmd_line = sys.argv[1:]  # fix for running tests with pytest
            else:
                cmd_line = sys.argv
        else:
            cmd_line = [s.strip() for s in cmd_line.split()]
            if len(cmd_line):
                entry_file = get_entry_file()
                if cmd_line[0] == entry_file:
                    return cmd_line[1:]
        return cmd_line

    def __init__(self,
                 cmd_line: Union[str, None] = None,  # representation of command line arguments
                 target: Callable = None,  # target callable
                 run_gui: bool = False):  # if True: start the parser as a GUI

        cmd_line = self._valid_cmd_line(cmd_line)
        if '--help' in cmd_line:
            print(self.cmd_line_help())
        else:
            if run_gui or '--gui' in cmd_line:
                self.kwargs = self.kwargs_class()
                self.run_gui(target)
            else:
                self.kwargs = self.kwargs_class(*cmd_line)
                if target:
                    self.kwargs(target)

    def as_dict(self):
        return self.kwargs._as_dict()

    def command(self, short=False, prog=False, path=True):
        return self.kwargs._command(short, prog, path)

    def parse(self, *cmd_line):
        self.kwargs._parse(*cmd_line)

    def run_gui(self, target):
        """ starts the GUI """
        arg_gui.ArgGui(parser=self, target=target).mainloop()

    def __call__(self, target):
        if target is None:
            raise ValueError(f"cannot call missing 'target'")
        self.parse(self.command())  # run through the validation again
        return target(**self.as_dict())

    def save(self, filename: str, mode: str = 'w'):
        """ saves command line to a file """
        cmd_line = self.command()
        with open(filename, mode) as f:
            f.write(cmd_line)


if __name__ == '__main__':
    pass
