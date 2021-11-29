import os
import sys

from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from typing import Callable, Union, Any, Dict

from pycicle import cmd_gui
from pycicle.basetypes import get_type_string
from pycicle.exceptions import ConfigError, ValidationError
from pycicle.tools.utils import MISSING, DEFAULT, get_entry_file, get_typed_class_attrs, count
from pycicle.tools.parsers import parse_bool, encode_bool, encode_datetime, parse_datetime, encode_date, parse_date, \
    encode_time, parse_time, parse_timedelta, encode_timedelta, parse_split, split_encode


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
        self.flags = None  # set in CmdParser.__init_subclass__
        self.positional = False  # set by CmdParser.__init_subclass__; meaning argument CAN be positional

    @property
    def full_name(self):
        return f"{self.cls.__name__}.{self.name}"

    @property
    def required(self):
        return self.default is MISSING

    @property
    def switch(self):
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
            if self.default is not MISSING:
                obj.__dict__[self.name] = self.default
                return self.default
            raise AttributeError(f"'{self.cls.__name__}' has no attribute '{self.name}'")

    def __set__(self, obj, value):
        """ see python descriptor documentation for the magic """
        try:
            if self.is_encoded(value):
                value = self.decode(value)
            obj.__dict__[self.name] = self.validate(value)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValidationError(f"error in '{self.name}' for value '{value}': " + str(error))

    def __delete__(self, obj):
        """ see python descriptor documentation for the magic """
        obj.__dict__.pop(self.name, None)
        if self.default is not MISSING:
            obj.__dict__[self.name] = self.default

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

        if count(existing.values(), key=lambda v: v.many) <= 1:
            if all(e.positional and not e.switch for e in existing.values()):
                self.positional = True

        if any(self.flags[-1] == e.flags[-1] for e in existing.values()):
            self.flags = self.flags[:-1]  # remove short flag

    def encode(self, value):
        """ creates str version of value, takes 'many' into account """
        if value is None or value is MISSING:
            return ''
        if self.many:
            return split_encode(self._encode(v) for v in value)
        return self._encode(value)

    def decode(self, string):
        """ creates value from str, takes 'many' into account """
        if self.type is not str and string == '':
            return self.default
        if self.many:
            return [self._decode(v) for v in parse_split(string)]
        return self._decode(string)

    def parse(self, value):
        if value == '':  # but flag was there
            if self.switch:
                return True
            raise ValidationError(f"missing value for '{self.name}'")
        if value is DEFAULT:  # flag was not there
            if self.default is MISSING:
                raise ValidationError(f"missing flag or value for '{self.name}'")
            return self.default
        return self.decode(value)

    def _validate(self, value):
        def cast(value):
            return value if type(value) is self.type else self.type(value)

        if self.many:
            value = [cast(v) for v in value]
        else:
            value = cast(value)

        if self.valid and not self.valid(value):
            raise ValueError(f"Invalid value: {str(value)} for argument '{self.name}'")
        return value

    def validate(self, value):
        """ performs validation and decoding of argument values """
        if value is MISSING:
            raise ValueError(f"error in '{self.name}': missing required value")
        if value is self.default:
            return value
        return self._validate(value)

    def _validate_default(self, value):
        if value is None or value is MISSING:
            return value
        try:
            return self._validate(value)
        except (TypeError, ValueError, AttributeError) as error:
            raise ConfigError(f"error in '{self.full_name}' for default '{value}': " + str(error))

    def _cmd_flag(self, short=False):
        """ return flag e.g. '--version', '-v' if short """
        if len(self.flags) == 1:
            return self.flags[0]
        return self.flags[1] if short else self.flags[0]

    def cmd(self, obj, short=False):
        """ creates command line part for this argument """
        value = self.__get__(obj)
        if self.switch:
            if value:
                return self._cmd_flag(short)
            return ''
        cmd_value = self.encode(value)
        if cmd_value == '':
            return ''
        if short and self.positional:
            return cmd_value
        return f"{self._cmd_flag(short)} {cmd_value}"

    def usage(self):
        usage = self.flags[0]
        if self.many:
            usage = usage + ' ...'
        if not self.required:
            usage = f"[{usage}]"
        return usage

    def option(self):
        flags = ', '.join(self.flags)
        type_ = get_type_string(self.type, short=True)
        posit = 'true'if self.positional else 'false'
        switch = 'true' if self.switch else 'false'
        if self.required:
            return f"{flags} ({type_}): positional: {posit}, switch: {switch}, {self.help}"
        else:
            return f"{flags} ({type_}): default: {self.default}, positional: {posit}, switch: {switch}, {self.help}"


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
        valid_arguments = {}
        for name, argument in get_typed_class_attrs(cls, Argument).items():
            argument.validate_config(valid_arguments)
            valid_arguments[name] = argument
        cls._arguments = valid_arguments

    @classmethod
    def _usage(cls):
        return f"{' '.join(arg.usage() for arg in cls._arguments.values())}"

    @classmethod
    def _options(cls, line_start=''):
        line_start = '\n' + line_start
        return line_start + line_start.join(arg.option() for arg in cls._arguments.values())

    def __init__(self, cmd_line: str = '', **kwargs):
        super().__init__()
        self._update(self._defaults())
        if cmd_line:
            self._parse(cmd_line)
        self._update(kwargs)

    def _parse(self, cmd_line):
        arg_defs = type(self)._arguments
        flag_lookup = {f: a for a in arg_defs.values() for f in a.flags}

        def get_args_kwargs(cmd_line):
            """ gets args and kwargs in encoded (str) form """
            cmd_line_list = parse_split(cmd_line)
            kwargs = {None: []}  # None key for positional arguments
            current_name = None  # positionals come first on cmd line
            for flag_or_value in cmd_line_list:
                if flag_or_value in flag_lookup:  # flag found
                    current_name = flag_lookup[flag_or_value].name
                    kwargs[current_name] = []  # stays if no values are found
                else:  # value found
                    kwargs[current_name].append(flag_or_value)
            return kwargs.pop(None), kwargs  # args, kwargs

        def get_positional_kwargs(pos_args):
            """ assigns positional string values to arguments """
            pos_arg_defs = []
            for name, arg_def in arg_defs.items():
                if name in kwargs:
                    break  # break on: first key already present
                pos_arg_defs.append(arg_def)

            pos_kwargs = {}
            try:  # note: if len(args) == 0, index error cannot occur
                while len(pos_args) and not pos_arg_defs[0].many:  # from left
                    pos_kwargs[pos_arg_defs.pop(0).name] = [pos_args.pop(0)]
                while len(pos_args) and not pos_arg_defs[-1].many:  # from right
                    pos_kwargs[pos_arg_defs.pop(-1).name] = [pos_args.pop(-1)]
            except IndexError:
                raise ValueError(f"too many positional arguments found: {cmd_line}")

            if len(pos_args) and len(pos_arg_defs) == 1:  # remaining
                pos_kwargs[pos_arg_defs[0].name] = pos_args
            return pos_kwargs

        args, kwargs = get_args_kwargs(cmd_line)
        kwargs.update(get_positional_kwargs(args))
        kwargs = {n: split_encode(l) for n, l in kwargs.items()}
        self._update({n: a.parse(kwargs.get(n, DEFAULT)) for n, a in arg_defs.items()})

    def _update(self, kwargs):
        """ fills self with values """
        for name, value in kwargs.items():
            setattr(self, name, value)

    def _defaults(self):
        return {n: a.default for n, a in self._arguments.items() if a.default is not MISSING}

    def _as_dict(self):
        return self.__dict__.copy()

    def _command(self, short=False, prog=False, path=True):
        """ creates the command line that can be used to call the parser:
            - short: short flags (e.g. -d) if possible,
            - prog: called file from command line is included"""
        try:
            cmds = [arg.cmd(self, short) for arg in self._arguments.values()]
        except AttributeError:
            return None
        else:
            cmd_line = ' '.join(c for c in cmds if c)
            if prog:
                return f"{get_entry_file(path)} {cmd_line}"
            return cmd_line


class CmdParser(object):
    """
    This class uses the arguments to parse and run the command line or start the GUI. A few notes:
     - The class itself stores the values for all the arguments. It subclasses Mapping and can be used
     as keyword arguments for a function (e.g. func(**parser)),
     - To enable this usage, all methods, class and other attributes start with an underscore,
     - the parser can call a target callable: if parser = CmdParser(): parser(func)
    """
    kwargs_class = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        cls.kwargs_class = cls._create_kwargs_class()
        cls.arguments = cls.kwargs_class._arguments

    @classmethod
    def _create_kwargs_class(cls):
        """ copies arguments and creates new Kwargs class with these arguments """
        return type(cls.__name__ + 'Kwargs', (Kwargs,), get_typed_class_attrs(cls, Argument))

    @classmethod
    def gui(cls, target=None):
        """ opens the GUI """
        return cls(target)(cmd_line='--gui')

    @classmethod
    def cmd(cls, target=None):
        """ reads arguments from command line """
        return cls(target)()

    @classmethod
    def parse(cls, *cmd_line, target=None):
        """ parses a command line from python (e.g. tests) """
        return cls(target)(cmd_line=' '.join(cmd_line))

    @classmethod
    def load(cls, filename: str, target=None):
        """ loads a command line from file """
        with open(filename, 'r') as f:
            cmd_line = f.read()
        return cls.parse(cmd_line, target=target)

    @classmethod
    def _prep_cmd_line(cls, cmd_line):
        if cmd_line is None:
            if "PYTEST_CURRENT_TEST" in os.environ:
                cmd_line_list = sys.argv[1:]  # fix for running tests with pytest
            else:
                cmd_line_list = sys.argv
        else:
            cmd_line_list = parse_split(cmd_line)

        if len(cmd_line_list):
            if cmd_line_list[0] == get_entry_file():
                cmd_line_list.pop(0)
        return split_encode(cmd_line_list)

    def __init__(self, __target: Callable = None, **sub_parsers: 'CmdParser'):
        self.target = __target  # double underscore to avoid name clashes with **sub_parsers
        self.sub_parsers = sub_parsers
        self.kwargs = self.kwargs_class()

    def __call__(self, cmd_line=None):
        cmd_line = self._prep_cmd_line(cmd_line)
        first, _, sub_cmd = cmd_line.partition(' ')
        if first == '--help':
            print(self.cmd_line_help())
        elif first == '--gui':
            self._run_gui()
        elif first in self.sub_parsers:
            self.sub_parsers[first](cmd_line=sub_cmd)
        else:
            self.kwargs._parse(cmd_line)
            self.run(do_raise=False)
        return self

    def run(self, do_raise=True):
        if self.target is not None:
            self.target(**self.kwargs._as_dict())
        elif do_raise:
            raise ValueError(f"cannot call missing target")

    def _run_gui(self):
        """ starts the GUI """
        cmd_gui.ArgGui(parser=self).mainloop()

    def command(self, short=False, prog=False, path=True):
        return self.kwargs._command(short, prog, path)

    def as_dict(self):
        return self.kwargs._as_dict()

    def save(self, filename: str, mode: str = 'w'):
        """ saves command line to a file """
        cmd_line = self.command()
        with open(filename, mode) as f:
            f.write(cmd_line)

    def usage_help(self, line_start=''):
        file = ''  if line_start else get_entry_file(path=False) + ' '
        line_start += '  '
        usage = f"{file}{self.kwargs_class._usage()}"
        for name, sub_parser in self.sub_parsers.items():
            usage += f"\n{line_start}{name}: {sub_parser.usage_help(line_start)}"
        return usage

    def options_help(self, line_start=''):
        line_start += '  '
        options = self.kwargs_class._options(line_start)
        for name, sub_parser in self.sub_parsers.items():
            options += f"\n{line_start}{name}:{sub_parser.options_help(line_start)}"
        return options

    def cmd_line_help(self):
        """ used by GUI to show help generated by argparse """
        return f"usage: {self.usage_help()}\n\noptions:\n  {self.options_help()}"


if __name__ == '__main__':
    pass
