import os
import unittest
from itertools import product

from pycicle import ArgParser, Argument
from pycicle import File, Folder, Choice


def yielder(arg):
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
            return ' '.join(arg._encode(v) for v in value)
        return arg.encode(value)

    cmd = ''
    for name, value in kwargs.items():
        arg = getattr(parser_class, name)
        value = create_value(arg, value)
        if arg.positional:
            cmd = cmd + f" {value}"
        else:
            if short:
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
        parser = parser_class(test_cmd, target=asserter)
        assert test_cmd == parser._command()


class TestArgParser(unittest.TestCase):

    def test_basic(self):
        class Parser(ArgParser):
            pass

        Parser('-h')

    def test_basic_keywords(self):
        callback_target = []

        class Parser(ArgParser):
            pos = Argument(int, positional=True)
            const = Argument(int, constant=True)
            default = Argument(int, default=0)
            required = Argument(int, required=True)
            valid = Argument(int, valid=lambda v: v < 10)
            many = Argument(int, many=True)
            with_callback = Argument(int, callback=lambda v, n: callback_target.extend([v, n]))

        asserter = args_asserter(pos=1, const=2, default=0, required=3, valid=4, many=[1, 2], with_callback=5)

        parser = Parser('1 -c 2 -r 3 -v 4 -m 1 2 --w 5', target=asserter)
        parser._call(asserter)
        assert callback_target[0] == 5

        for kwargs in dict_product(pos=(-1, 0, 1), const=7, default=(-1, 0, 1), required=(-1, 0, 1),
                                   valid=(-1, 0, 1), many=([9, 11],), with_callback=(-1, 0, 1)):
            asserter = args_asserter(**kwargs)

            cmd = make_test_command(Parser, kwargs)
            parser = Parser(cmd, target=asserter)
            assert parser._command(short=False) == cmd
            assert parser._command(short=True) == make_test_command(Parser, kwargs, short=True)

    def test_valid(self):
        class Parser(ArgParser):
            units = Argument(int, valid=lambda v: v >= 0)
            name = Argument(str, valid=lambda v: len(v) >= 3)

        for kwargs in dict_product(units=range(-3, 3), name=('an', 'ann', 'anna')):
            asserter = args_asserter(**kwargs)
            cmd = make_test_command(Parser, kwargs)
            if kwargs['units'] < 0 or len(kwargs['name']) < 3:
                with self.assertRaises(ValueError):
                    Parser(cmd, target=asserter)
            else:
                Parser(cmd, target=asserter)

    def test_datetime_types_and_defaults(self):
        from datetime import datetime, time, date, timedelta

        class Parser(ArgParser):
            datetime_ = Argument(datetime, default=datetime(1999, 6, 8, 12, 12, 12))
            timedelta_ = Argument(timedelta, default=timedelta(hours=1, minutes=2, seconds=3))
            date_ = Argument(date, default=date(1999, 6, 8))
            time_ = Argument(time, default=time(12, 12, 12))

        defaults = {arg.name: arg.default for arg in Parser._arguments}
        asserter = args_asserter(**defaults)

        test_cmd = make_test_command(Parser, defaults)
        parser = Parser(test_cmd,
                        target=asserter)
        real_cmd = parser._command()
        assert test_cmd == real_cmd
        parser2 = Parser(use_app=False,
                         target=asserter)
        assert test_cmd == parser2._command()

    def test_bool(self):
        class Parser(ArgParser):
            one = Argument(bool)
            two = Argument(bool, many=2)

        assert_product(Parser, one=(False, True),
                       two=([False, False], [True, False]))

    def test_choice(self):
        class Parser(ArgParser):
            one = Argument(Choice(1, 2, 3))
            two = Argument(Choice(1, 2, 3), many=2)

        assert_product(Parser, one=(1, 2), two=([1, 3], [2, 1]))

    def test_files(self):
        class Parser(ArgParser):
            one = Argument(File('.txt', exists=False))
            two = Argument(File('.py', exists=True))
            three = Argument(File('.txt', exists=False), many=2)

        assert_product(Parser, one=('c:\\does_not_exist.txt', '..\\unittests\\does_not_exist.txt'),
                               two=(__file__, '..\\unittests\\test_clapy.py'),
                               three=(['c:\\does_not_exist.txt', '..\\unittests\\does_not_exist.txt'],))

    def test_folders(self):
        class Parser(ArgParser):
            one = Argument(Folder(exists=False))
            two = Argument(Folder(exists=True))
            three = Argument(Folder(exists=False), many=2)

        assert_product(Parser, one=('c:\\does_not_exist', '..\\unittests\\does_not_exist'),
                       two=(os.path.dirname(__file__), '..\\unittests'),
                       three=(['c:\\does_not_exist', '..\\unittests\\does_not_exist'],))


if __name__ == '__main__':
    pass
