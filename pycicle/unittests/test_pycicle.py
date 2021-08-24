import os
import unittest

from pycicle import ArgParser, Argument
from pycicle import File, Folder, Choice
from pycicle.unittests.testing_tools import dict_product, make_test_command, args_asserter, assert_product


class TestArgParser(unittest.TestCase):

    def test_basic(self):
        class Parser(ArgParser):
            pass

        Parser('-h')

    def test_basic_keywords(self):
        callback_target = []

        class Parser(ArgParser):
            pos = Argument(int, positional=True)
            default = Argument(int, default=0)
            required = Argument(int, required=True)
            valid = Argument(int, valid=lambda v: v < 10)
            many = Argument(int, many=True)
            with_callback = Argument(int, callback=lambda v, ns: callback_target.extend([v, ns]))

        asserter = args_asserter(pos=1, default=0, required=3, valid=4, many=[1, 2], with_callback=5)

        parser = Parser('1 -r 3 -v 4 -m 1 2 --w 5', target=asserter)
        parser(asserter)
        assert callback_target[0] == 5

        for kwargs in dict_product(pos=(-1, 0, 1), default=(-1, 0, 1), required=(-1, 0, 1),
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

    def test_default(self):
        class Parser(ArgParser):
            name = Argument(str)
            units = Argument(int, default=3)

        parser = Parser('-n bob')

        assert parser.name == 'bob'
        assert parser.units == 3

    def test_novalue(self):
        class Parser(ArgParser):
            name = Argument(str, default='bob', novalue='ann')
            units = Argument(int, novalue=3)

        parser = Parser('--units')

        assert parser.name == 'bob'
        assert parser.units == 3

        parser = Parser('--name')

        assert parser.name == 'ann'
        assert parser.units is None

        with self.assertRaises(RuntimeError):
            class Parser(ArgParser):
                name = Argument(int, novalue='ann')

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
        parser2 = Parser(use_gui=False,
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
                       two=(__file__, '..\\unittests\\test_pycicle.py'),
                       three=(['c:\\does_not_exist.txt', '..\\unittests\\does_not_exist.txt'],))

    def test_folders(self):
        class Parser(ArgParser):
            one = Argument(Folder(exists=False))
            two = Argument(Folder(exists=True))
            three = Argument(Folder(exists=False), many=2)

        assert_product(Parser, one=('c:\\does_not_exist', '..\\unittests\\does_not_exist'),
                       two=(os.path.dirname(__file__), '..\\unittests'),
                       three=(['c:\\does_not_exist', '..\\unittests\\does_not_exist'],))

    def test_positional_ordering(self):
        """ check whether positional arguments after non-positional arguments raise errors """
        class Parser1(ArgParser):  # must be OK
            one = Argument(int, positional=True)
            two = Argument(int, positional=False)

        with self.assertRaises(ValueError):
            class Parser2(ArgParser):
                one = Argument(int, positional=False)
                two = Argument(int, positional=True)

    def test_callback_adding_extra_arg(self):
        def callback(value, namespace):
            namespace.extra = value

        class Parser(ArgParser):  # must be OK
            one = Argument(int, callback=callback)

        parser = Parser({'one': 1})

        assert parser.extra == 1

    def test_command_line(self):
        pass






if __name__ == '__main__':
    pass
