import inspect

from pycicle.document import Chapter, ItemList, Document
from pycicle.tools import MISSING


def get_name(item):
    try:
        return item.string()
    except AttributeError:
        try:
            return item.__name__
        except AttributeError:
            return str(item)


def name_str(arg):
    return arg.name


def flag_str(arg):
    if arg.positional:
        return ''
    return f"({', '.join(arg.flags)})"


def type_str(arg):
    if arg.many:
        return f"[{get_name(arg.type)}]"
    return get_name(arg.type)


def req_str(arg):
    return str(arg.required).lower()


def count_str(arg):
    if isinstance(arg.many, bool):
        return ''
    return str(arg.many)


def default_str(arg):
    if arg.default is None:
        return ''
    return arg.encode(arg.default)


def novalue_str(arg):
    if arg.novalue is MISSING:
        return ''
    return arg.encode(arg.novalue)


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
    return _func_str(arg.valid)


str_funcs = dict(
    flags=flag_str,
    name=name_str,
    type=type_str,
    count=count_str,
    required=req_str,
    default=default_str,
    novalue=novalue_str,
    valid=valid_str,
)


def get_parser_help(parser_class):
    option_help = ItemList(intro='help for the options',
                           items={arg.name: arg.help for arg in parser_class._arguments if arg.help},
                           extra='more help can be found under the help buttons next to the options')
    command_help = 'command line definition:\n\n' +parser_class._cmd_help()
    chapters = [Chapter('Option Help', content=option_help('-'))(),
                Chapter('Command Line', content=command_help)()]
    document = Document(title=parser_class.__name__,
                        intro=parser_class.__doc__.strip(),
                        chapters=chapters)
    return document()


def get_argument_help(arg, error):
    arg_specs= ItemList(items={name: func(arg) for name, func in str_funcs.items()})
    chapters = [Chapter('Help', content=arg.help)(),
                Chapter('Specifications', content=arg_specs(''))()]
    if error:
        chapters.append(Chapter('Error', content=str(error))())
    document = Document(title=f"Option: {arg.name}",
                        intro=f"Specifications for '{arg.name}':",
                        chapters=chapters)
    return document()
