import os
import sys

from dataclasses import dataclass
from functools import cached_property
from inspect import Parameter, signature
from typing import Callable, Any, Mapping, Tuple, Sequence

from pycicle import cmd_gui
from pycicle.custom_types import get_type_string
from pycicle.exceptions import ConfigError, ValidationError
from pycicle.tools.utils import MISSING, DEFAULT, get_entry_file, get_typed_class_attrs, count
from pycicle.tools.parsers import quote_split, quote_join, default_type_codecs


@dataclass
class Argument(object):
    type: Callable
    flags: Tuple[str, ...] = None
    many: bool = False
    default: Any = MISSING
    valid: Callable[[Any], bool] = None
    help: str = ""
    name: str = ""  # set in __set_name__

    type_codecs = default_type_codecs.copy()
    basic_types = (str, int, float, bool)

    reserved = {'help', 'gui'}

    @classmethod
    def types(cls):
        return cls.basic_types + tuple(cls.type_codecs)  # keys of type_codecs are classes

    @classmethod
    def set_codec(cls, type, encode, decode):
        cls.type_codecs[type] = (encode, decode)

    def __post_init__(self):
        """ mainly sets the encoders and decoders for the argument """
        encode, decode = self.type_codecs.get(self.type, (None, None))
        self._encode = encode or str  # str is default
        self._decode = decode or self.type  # self.type is default (int('3') == 3)
        self.positional = False  # set by validate_config(); meaning argument CAN be positional

    @property
    def full_name(self):
        return f"{self.cls.__name__}.{self.name}"

    @property
    def required(self):
        return self.default is MISSING

    @property
    def switch(self):
        return self.type is bool and self.default is False  # so self.many must also be False

    def __set_name__(self, cls, name):
        """ descriptor method to set the name to the attribute name in the owner class """
        self.cls = cls
        self.name = name

    def __get__(self, obj, cls=None):
        """ see python descriptor docs for the magic """
        if obj is None:
            return self
        try:
            return obj.__arg_values__[self.name]
        except KeyError:
            if self.default is not MISSING:
                obj.__arg_values__[self.name] = self.default
                return self.default
            raise AttributeError(f"'{self.cls.__name__}' has no attribute '{self.name}'")

    def __set__(self, obj, value):
        """ see python descriptor documentation for the magic """
        try:
            obj.__arg_values__[self.name] = self.validate(value)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValidationError(f"error in '{self.name}' for value '{value}': " + str(error))

    def __delete__(self, obj):
        """ see python descriptor documentation for the magic """
        obj.__arg_values__.pop(self.name, None)
        if self.default is not MISSING:
            obj.__arg_values__[self.name] = self.default

    def validate_config(self, existing):
        """
        Called in __init_subclass__ of owner class because self.name must be set to give clearer error messages and
        python __set_name__ changes all exceptions to (somewhat vague) RuntimeError.
        """
        if not issubclass(self.type, self.types()):
            raise TypeError(f"invalid type '{self.type.__name__}' in '{self.full_name}'")

        if self.name in self.reserved:
            raise ConfigError(f"Argument name '{self.name}' is reserved")

        if self.name.startswith('_'):
            raise ConfigError(f"Argument name '{self.name}' cannot start with an '_' (to prevent name conflicts)")

        self.default = self._validate_default(self.default)

        if count(existing.values(), key=lambda v: v.many) <= 1:
            if all(e.positional and not e.switch for e in existing.values()):
                self.positional = True  # this means the argument CAN be positional

        self.flags = self._validate_flags(existing)

    def encode(self, value):
        """ creates str version of value, takes 'many' into account """
        if value is None or value is MISSING:
            return ''
        if self.many:
            return quote_join(self._encode(v) for v in value)
        return self._encode(value)

    def decode(self, string_s):
        """ creates value from str, takes 'many' into account """
        if self.many:
            if isinstance(string_s, str):
                string_s = string_s.split()
            if not len(string_s):
                return self.default
            return [self._decode(s) for s in string_s]
        else:
            if self.type is not str and string_s == '':
                return self.default
            return self._decode(string_s)

    def parse_list(self, value):
        """ only used in parser """
        if value is DEFAULT:  # flag was not there
            if self.default is MISSING:
                raise ValidationError(f"missing flag or value for '{self.name}'")
            return self.default
        if not len(value):  # but flag was there
            if self.switch:
                return True
            raise ValidationError(f"missing value for '{self.name}'")
        return self.decode(value if self.many else value[0])

    def _validate_flags(self, existing):
        def valid_format(flag):
            flag = flag.strip()
            if flag.startswith('--'):
                if len(flag) < 3:
                    raise ConfigError(f"flag '{flag}' too short in '{self.name}'")
            elif flag.startswith('-'):
                if len(flag) != 2:
                    raise ConfigError(f"single underscore flag '{flag}' should be a '-' and a character")
            else:
                raise ConfigError(f"invalid flag '{flag}': all flags must start with a single or double '-'")
            return flag

        def remove_existing(flags):
            for arg in existing.values():
                for flag in flags[:]:
                    if flag in arg.flags:
                        flags.remove(flag)
            if not len(flags):
                raise ConfigError(f"Argument '{self.name}' has no flags, all configured flags were used by other arguments")
            return tuple(flags)

        if self.flags:
            flags = [valid_format(f) for f in self.flags]
        else:
            flags = ['--' + self.name, '-' + self.name[0]]
        return remove_existing(flags)

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
        """ return flag e.g. '--version', '-v' if short == True"""
        return min(self.flags, key=len) if short else max(self.flags, key=len)

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
        usage = self._cmd_flag()
        if self.many:
            usage = usage + ' ...'
        if not self.required:
            usage = f"[{usage}]"
        return usage

    def option(self):
        flags = ', '.join(self.flags)
        type_ = get_type_string(self.type, short=True)
        posit = 'true' if self.positional else 'false'
        switch = 'true' if self.switch else 'false'
        if self.required:
            return f"{flags} ({type_}): positional: {posit}, switch: {switch}, {self.help}"
        else:
            return f"{flags} ({type_}): default: {self.default}, positional: {posit}, switch: {switch}, {self.help}"


class KeywordArguments(Mapping):
    """
    This class uses the arguments to parse and run the command line or start the GUI. A few notes:
     - The class itself stores the values for all the arguments,
     - To enable this usage, all methods, class and other attributes start with an underscore,
    """
    _arguments = None  # overridden in __init_subclass__

    def __init_subclass__(cls, **kwargs):
        """ mainly initialises the argparse.ArgumentParser and adds arguments to the parser """
        super().__init_subclass__(**kwargs)
        valid_args = {}
        for name, argument in get_typed_class_attrs(cls, Argument).items():
            argument.validate_config(valid_args)
            valid_args[name] = argument
        cls._arguments = valid_args

    @classmethod
    def _defaults(cls):
        return {n: a.default for n, a in cls._arguments.items() if a.default is not MISSING}

    def __init__(self, **kwargs):
        self.__arg_values__ = {}
        self._update(**self._defaults())
        self._update(**kwargs)

    def __len__(self):
        return len(self.__arg_values__)

    def __iter__(self):
        yield from self.__arg_values__

    def __getitem__(self, key):
        return self.__arg_values__[key]

    def _update(self, **kwargs):
        """ fills self with values via descriptors """
        for name, value in kwargs.items():
            setattr(self, name, value)


class CmdParser(object):
    """
    This class is the Parser API. Actual parsing takes place in the Kwargs class, where also the parsed values are stored.
    """
    keyword_argument_class = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        cls.keyword_argument_class = cls._make_keyword_argument_class()
        cls.arguments = cls.keyword_argument_class._arguments  # convenience shortcut

    @classmethod
    def _make_keyword_argument_class(cls):
        """ moves arguments to new KeywordArguments class """
        arguments = get_typed_class_attrs(cls, Argument)
        for attr_name in arguments:
            delattr(cls, attr_name)  # remove from this class
        return type(cls.__name__ + 'KeywordArguments', (KeywordArguments,), arguments)

    @classmethod
    def load(cls, filename: str, target=None):
        """ loads a command line from file """
        with open(filename, 'r') as f:
            cmd_line = f.read()
        return cls(target).parse(cmd_line)

    @classmethod
    def from_callable(cls, func):
        def get_type(p):
            if get_many(p):
                try:
                    return p.annotation.__args__[0]
                except (AttributeError, IndexError):
                    raise TypeError(f"List parameter must have element type (e.g. 'List[int]', not 'List' or 'list')")
            return p.annotation  # type exceptions will be handled by the Argument class

        def get_many(p):
            try:
                return p.annotation.__origin__ is list
            except AttributeError:
                return False

        def get_default(p):
            if p.default is Parameter.empty:
                return MISSING
            return p.default

        def get_class_name(f):
            return ''.join(n.capitalize() for n in f.__qualname__.split('.'))

        arguments = {}
        for name, param in signature(func).parameters.items():
            arguments[name] = Argument(type=get_type(param),
                                       many=get_many(param),
                                       default=get_default(param))

        return type(get_class_name(func), (CmdParser,), arguments)(func)  # create class and initialize with func as target

    @classmethod
    def _remove_entry_file(cls, cmd_line_list):
        if len(cmd_line_list):
            if cmd_line_list[0] in (get_entry_file(path=False),
                                    get_entry_file(path=True)):
                cmd_line_list.pop(0)
        return cmd_line_list

    @classmethod
    def get_cmd_from_sys(cls):
        if "PYTEST_CURRENT_TEST" in os.environ:
            cmd_list = sys.argv[1:]  # fix for running tests with pytest
        else:
            cmd_list = sys.argv
        return cls._remove_entry_file(cmd_list)

    @classmethod
    def normalize(cls, cmd_line):
        return cls._remove_entry_file(quote_split(cmd_line))

    def __init__(self, __target: Callable = None, **sub_parsers: 'CmdParser'):
        self.target = __target  # double underscore to avoid name clashes with **sub_parsers
        self.parent = None
        self.sub_parsers = self._link_sub_parsers(sub_parsers)
        self.keyword_arguments = self.keyword_argument_class()

    def _link_sub_parsers(self, sub_parsers):
        for name, sub_parser in sub_parsers.items():
            if sub_parser.parent:
                raise ValueError(f"sub_parser instance for '{name}' cannot be used in multiple parent parsers")
            sub_parser.parent = self
        return sub_parsers

    def _parse_list(self, cmd_list):
        arg_defs = self.arguments
        flag_lookup = {f: a for a in arg_defs.values() for f in a.flags}

        def get_args_kwargs(cmd_list):
            """ gets args and kwargs in encoded (str) form """
            kwargs = {None: []}  # None key for positional arguments
            current_name = None  # positionals come first on cmd line
            for flag_or_value in cmd_list:
                if flag_or_value in flag_lookup:  # flag found
                    current_name = flag_lookup[flag_or_value].name
                    kwargs[current_name] = []  # stays empty if no values are found
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
                raise ValueError(f"too many positional arguments found: {cmd_list}")

            if len(pos_args) and len(pos_arg_defs) == 1:  # remaining; only if many is True
                pos_kwargs[pos_arg_defs[0].name] = pos_args
            return pos_kwargs

        args, kwargs = get_args_kwargs(cmd_list)
        kwargs.update(get_positional_kwargs(args))
        self.update(**{n: a.parse_list(kwargs.get(n, DEFAULT)) for n, a in arg_defs.items()})

    @property
    def name(self):
        return self.file(path=False).rpartition('.')[0]

    def file(self, path=True):
        return get_entry_file(path)

    @cached_property
    def sub_path(self):
        if self.parent:
            for sub_key, sub_process in self.parent.sub_parsers.items():
                if sub_process is self:
                    if self.parent.sub_path:
                        return f"{self.parent.sub_path} {sub_key}"
                    return sub_key
        return None

    def __call__(self, cmd=None, run=True):
        if cmd is None:
            cmd_list = self.get_cmd_from_sys()
        else:
            cmd_list = self.normalize(cmd)
        first = cmd_list[0] if cmd_list else None
        if first == '--help':
            print(self.help())
        elif first == '--gui':
            self.gui()
        elif first in self.sub_parsers:
            self.sub_parsers[first](quote_join(cmd_list[1:]))
        else:
            self._parse_list(cmd_list)
            if run:
                self.run(do_raise=False)
        return self

    def command(self, short=False, file=False, path=True, list=False):
        """ creates the command line that can be used to call the parser:
            - short: short flags (e.g. -d) or positional values if possible,
            - file: prepend the file name before the command
            - path: the file above is replaced with the full path to the file
            - list: the command is returned  as a list string (with [])
        """
        try:
            cmds = [arg.cmd(self.keyword_arguments, short) for arg in self.arguments.values()]
        except AttributeError:
            return None
        else:
            cmd = ' '.join(c for c in cmds if c)
            if self.sub_path:
                cmd = f"{self.sub_path} {cmd}"
            if file:
                cmd = f"{self.file(path)} {cmd}"
            if list:
                cmd = str(quote_split(cmd))
            return cmd

    def update(self, **kwargs):
        self.keyword_arguments._update(**kwargs)

    def cmd(self):
        """ reads arguments from command line """
        return self.__call__(cmd=None)

    def gui(self):
        """ opens the GUI """
        return cmd_gui.ArgGui(parser=self).mainloop()

    def parse(self, *cmds, run=False):
        """ parses a command line from python (e.g. tests) """
        return self.__call__(' '.join(cmds), run=run)

    def run(self, do_raise=True):
        """ runs the target with current argument values """
        if self.target is not None:
            self.target(**self.keyword_arguments)
        elif do_raise:
            raise ValueError(f"cannot call missing target")

    def prompt(self, name=None):
        """ runs the target from a command prompt """
        prompt = (name or self.name) + '>'
        while True:
            try:
                print(prompt, end=' ')
                self.__call__(input())
            except KeyboardInterrupt:
                sys.exit()
            except Exception as e:
                print('error:', str(e))

    def save(self, filename: str, **kwargs):
        with open(filename, 'w') as f:
            f.write(self.command(**kwargs))

    def dict(self):
        return dict(self.keyword_arguments)

    def help(self):
        """ used by GUI and command line '--help' to show help """
        return f"usage: {self._usage_help()}\n\noptions:\n  {self._options_help()}"

    def _usage_help(self, line_start=''):
        """ usage info similar to other command line parsers """
        file = '' if line_start else get_entry_file(path=False) + ' '
        line_start += '  '
        usage = f"{file}{' '.join(arg.usage() for arg in self.arguments.values())}"
        for name, sub_parser in self.sub_parsers.items():
            usage += f"\n{line_start}{name}: {sub_parser._usage_help(line_start)}"
        return usage

    def _options_help(self, line_start=''):
        """ help on options similar to other command line parsers """
        line_start = f"\n{line_start} "
        options = line_start + line_start.join(arg.option() for arg in self.arguments.values())
        for name, sub_parser in self.sub_parsers.items():
            options += f"\n{line_start}{name}:{sub_parser._options_help(line_start)}"
        return options


if __name__ == '__main__':
    pass
