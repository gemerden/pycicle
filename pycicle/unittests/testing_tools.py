from itertools import product

from pycicle.tools.parsers import quote_join


def yielder(arg):
    if isinstance(arg, str):
        yield arg
    try:
        yield from arg
    except TypeError:
        yield arg


def dict_product(**iterators):
    iterators = {n: yielder(it) for n, it in iterators.items()}
    names = list(iterators)
    for values in product(*iterators.values()):
        yield dict(zip(names, values))


def make_test_command(parser_class, kwargs, short=False):
    """ somewhat more limited then real function """

    def create_value(arg, value):
        if isinstance(value, (list, tuple)):
            return quote_join(arg._encode(v) for v in value)
        return arg.encode(value)

    cmd = ''
    for name, value in kwargs.items():
        arg = getattr(parser_class.keyword_argument_class, name)
        value = create_value(arg, value)
        if short:
            if arg.positional:
                cmd = cmd + f" {value}"
            else:
                cmd = cmd + f" -{name[0]} {value}"  # can create doubles
        else:
            cmd = cmd + f" --{name} {value}"
    return cmd.strip()


def args_asserter(**expected):
    def do_assert(**created):
        if len(expected) != len(created):
            raise AssertionError(f"incorrect number of arguments: {len(created)} != {len(expected)}")
        for name, value in expected.items():
            if value != created[name]:
                raise AssertionError(f"incorrect value for '{name}': {created[name]} != {value}")

    return do_assert


def assert_product(parser_class, **iterators):
    for kwargs in dict_product(**iterators):
        asserter = args_asserter(**kwargs)
        test_cmd = make_test_command(parser_class, kwargs)
        parser = parser_class(asserter).parse(test_cmd, run=True)
        assert test_cmd == parser.command()


if __name__ == '__main__':
    print(list(dict_product(a=1, b=(2, 3))))