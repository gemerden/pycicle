import inspect

from pycicle.tools import MISSING

_arg_help_template = \
"""
name: {name}
{help}

Options:
{definition}
{error}
"""

_parser_help_template = \
"""
{title}
{upper_line}
{class_doc}

Arguments:
{upper_line}
{definitions}

* = required

Command Line:
{upper_line}
{parser_help}
"""

upper_line = 120 * chr(8254)


_arg_def_template = "{name}{flags}: {type}{count}{default}{novalue}{valid}{help}"


def get_name(item):
    try:
        return item.string()
    except AttributeError:
        try:
            return item.__name__
        except AttributeError:
            return str(item)


def name_str(arg):
    if arg.required:
        return f"*{arg.name}"
    return arg.name


def flag_str(arg):
    if arg.positional:
        return ''
    return f"({', '.join(arg.flags)})"


def type_str(arg):
    if arg.many:
        return f"type: [{get_name(arg.type)}]"
    return 'type: ' + get_name(arg.type)


def req_str(arg):
    return str(arg.required).lower()


def count_str(arg):
    if isinstance(arg.many, bool):
        return ''
    return ' count: ' + str(arg.many)


def default_str(arg):
    if arg.default is None:
        return ''
    return ' default: ' + arg.encode(arg.default)


def novalue_str(arg):
    if arg.novalue is MISSING:
        return ''
    return ' novalue: ' + arg.encode(arg.novalue)


def _func_str(func):
    if not func:
        return 'none'
    name = func.__qualname__
    if '<lambda>' in name:
        src = inspect.getsource(func)
        _, _, code = src.partition(':')
        return code.strip()
    return name


def valid_str(arg):
    if not arg.valid:
        return ''
    return ' valid: '+_func_str(arg.valid)


def help_str(arg):
    if not arg.help.strip():
        return ''
    return ' help: ' + arg.help


str_funcs = dict(
    flags=flag_str,
    name=name_str,
    type=type_str,
    count=count_str,
    default=default_str,
    novalue=novalue_str,
    valid=valid_str,
    help=help_str,
)


def _get_arg_def(arg):
    str_dict = {name: func(arg) for name, func in str_funcs.items()}
    return _arg_def_template.format(**str_dict)


def get_parser_help(parser_class):
    sep = '\n   '
    definitions = '   ' + sep.join(map(_get_arg_def, parser_class._arguments))
    return _parser_help_template.format(title=parser_class.__name__,
                                        class_doc=parser_class.__doc__.strip(),
                                        definitions=definitions,
                                        parser_help=parser_class._cmd_help(),
                                        upper_line=upper_line)


def get_argument_help(argument, error):
    error_line = f"\nError: {error}" if error else ''
    return _arg_help_template.format(name=argument.name,
                                     help=argument.help,
                                     error=error_line,
                                     definition=_get_arg_def(argument))
