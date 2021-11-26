import inspect

from pycicle.tools.utils import MISSING
from pycicle.tools.document import Document, Chapter, ItemList


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
    return f"{', '.join(arg.flags)}"


def type_str(arg):
    if arg.many:
        return f"[{get_name(arg.type)}]"
    return get_name(arg.type)


def req_str(arg):
    return str(arg.required).lower()


def many_str(arg):
    return str(arg.many).lower()


def default_str(arg):
    if arg.default is None or arg.default is MISSING:
        return ''
    return arg.encode(arg.default)


def _func_str(func):
    if not func:
        return 'none'
    if func.__doc__:
        return f"{func.__qualname__}: {func.__doc__}"
    return '\n' + inspect.getsource(func)


def valid_str(arg):
    if arg.valid is None:
        return ''
    return _func_str(arg.valid)


str_funcs = dict(
    flags=flag_str,
    name=name_str,
    type=type_str,
    many=many_str,
    required=req_str,
    default=default_str,
    valid=valid_str,
)


def get_parser_help(parser, **kwargs):
    command_help = f"current: {parser.command(prog=True, path=False)}\n\n{parser.cmd_line_help()}"
    chapters = [Chapter('Command Line', content=command_help)(**kwargs)]
    document = Document(title=type(parser).__name__,
                        intro=type(parser).__doc__.strip(),
                        chapters=chapters,
                        extro='More help can be found under the help buttons next to the options.')
    return document(**kwargs)


def get_argument_help(argument, error=None, **kwargs):
    arg_specs = ItemList(items={name: func(argument) for name, func in str_funcs.items()})
    chapters = [Chapter('Help', content=argument.help)(**kwargs),
                Chapter('Specifications', content=arg_specs(''))(**kwargs)]
    if error:
        chapters.insert(0, Chapter('ERROR', content=str(error))(**kwargs))
    document = Document(title=f"Option: {argument.name}",
                        intro=f"details of '{argument.name}'",
                        chapters=chapters)
    return document(**kwargs)
