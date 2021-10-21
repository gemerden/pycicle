import os
import unittest
from datetime import datetime, timedelta, date, time

from pycicle import CmdParser, Argument
from pycicle import File, Folder, Choice
from pycicle.exceptions import ConfigError
from pycicle.tools.utils import MISSING
from pycicle.unittests.testing_tools import dict_product, make_test_command, args_asserter, assert_product


class TestArgParser(unittest.TestCase):

    def test_basic(self):
        class Parser(CmdParser):
            pass

        Parser.parse('--help')
        import subprocess
        subprocess.run(['python', __file__, "-h"])

    def test_target(self):
        """ test whether target gets called """
        result = {}

        def target(**kwargs):
            result.update(kwargs)

        class Parser(CmdParser):
            arg = Argument(int)

        Parser.parse('--arg 1', target=target)
        assert result == {'arg': 1}

    def test_basic_keywords(self):

        class Parser(CmdParser):
            default = Argument(int, default=0)
            valid = Argument(int, valid=lambda v: v < 10)
            many = Argument(int, many=True)

        asserter = args_asserter(default=0, valid=4, many=[1, 2])

        parser = Parser.parse('-v 4 -m "1" 2', target=asserter)

        for kwargs in dict_product(default=(-1, 0, 1), valid=(-1, 0, 1), many=([9, 11],)):
            asserter = args_asserter(**kwargs)

            cmd = make_test_command(Parser, kwargs)
            parser = Parser.parse(cmd, target=asserter)
            assert parser.command(short=False) == cmd
            assert parser.command(short=True) == make_test_command(Parser, kwargs, short=True)

    def test_positionals(self):
        class Parser(CmdParser):
            a = Argument(int, many=True)

        def target(**kwargs):
            assert kwargs == dict(a=[1, 2, 3, 4])

        Parser.parse('1 2 3 4', target=target)

        class Parser(CmdParser):
            a = Argument(int, many=False)
            b = Argument(int, many=True)
            c = Argument(int, many=False)

        def target(**kwargs):
            assert kwargs == dict(a=1, b=[2, 3], c=4)

        Parser.parse('1 2 3 4', target=target)

        class Parser(CmdParser):
            b = Argument(int, many=True)
            c = Argument(int, many=True)

        with self.assertRaises(ValueError):
            Parser.parse('1 2', target=target)

        class Parser(CmdParser):
            a = Argument(int, many=False)
            b = Argument(int, many=True)
            c = Argument(int, many=True)
            d = Argument(int, many=False)

        with self.assertRaises(ValueError):
            Parser.parse('1 2 3 4, 5', target=target)

    def test_required(self):
        class Parser(CmdParser):
            a = Argument(int)
            b = Argument(int, default=0)

        Parser.parse('-a 1')

        with self.assertRaises(ValueError):
            Parser.parse('-b 1')

    def test_valid(self):
        class Parser(CmdParser):
            units = Argument(int, valid=lambda v: v >= 0)
            name = Argument(str, valid=lambda v: len(v) >= 3)

        for kwargs in dict_product(units=range(-3, 3), name=('an', 'ann', 'anna')):
            asserter = args_asserter(**kwargs)
            cmd = make_test_command(Parser, kwargs)
            if kwargs['units'] < 0 or len(kwargs['name']) < 3:
                with self.assertRaises(ValueError):
                    Parser.parse(cmd, target=asserter)
            else:
                Parser.parse(cmd, target=asserter)

    def test_default(self):
        class Parser(CmdParser):
            name = Argument(str)
            units = Argument(int, default=3)

        parser = Parser.parse('-n bob')

        assert parser.kwargs.name == 'bob'
        assert parser.kwargs.units == 3

    def test_missing_value(self):
        class Parser(CmdParser):
            x = Argument(bool, default=False)
            y = Argument(bool, default=False)
            z = Argument(bool, default=None)

        parser = Parser.parse('-x')

        assert parser.kwargs.x is True
        assert parser.kwargs.y is False
        assert parser.kwargs.z is None

        with self.assertRaises(ValueError):
            parser = Parser.parse('-z')

    def test_datetime_types_and_defaults(self):
        from datetime import datetime, time, date, timedelta

        class Parser(CmdParser):
            datetime_ = Argument(datetime, default=datetime(1999, 6, 8, 12, 12, 12))
            timedelta_ = Argument(timedelta, default=timedelta(hours=1, minutes=2, seconds=3))
            date_ = Argument(date, default=date(1999, 6, 8))
            time_ = Argument(time, default=time(12, 12, 12))

        defaults = {name: arg.default for name, arg in Parser.arguments.items()}
        asserter = args_asserter(**defaults)

        test_cmd = make_test_command(Parser, defaults)
        parser = Parser.parse(test_cmd,
                        target=asserter)
        assert test_cmd == parser.command()

        parser2 = Parser.parse(target=asserter)
        assert test_cmd == parser2.command()

    def test_bool(self):
        class Parser(CmdParser):
            one = Argument(bool)
            two = Argument(bool, many=True)

        assert_product(Parser, one=(False, True),
                       two=([False, False], [True, False]))

    def test_unrequired_positional(self):
        class Parser(CmdParser):
            one = Argument(int, default=1)

        asserter = args_asserter(one=1)
        parser = Parser.parse(target=asserter)

    def test_choice(self):
        class Parser(CmdParser):
            one = Argument(Choice(1, 2, 3))
            two = Argument(Choice(1, 2, 3), many=True)

        assert_product(Parser, one=(1, 2), two=([1, 3], [2, 1]))

    def test_files(self):
        class Parser(CmdParser):
            one = Argument(File('.txt', existing=False))
            two = Argument(File('.py', existing=True))
            three = Argument(File('.txt', existing=False), many=True)

        assert_product(Parser, one=('c:\\does_not_exist.txt', '..\\unittests\\does_not_exist.txt'),
                       two=(__file__, '..\\unittests\\test_pycicle.py'),
                       three=(['c:\\does_not_exist.txt', '..\\unittests\\does_not_exist.txt'],))

    def test_folders(self):
        class Parser(CmdParser):
            one = Argument(Folder(existing=False))
            two = Argument(Folder(existing=True))
            three = Argument(Folder(existing=False), many=True)

        assert_product(Parser, one=('c:\\does_not_exist', '..\\unittests\\does_not_exist'),
                       two=(os.path.dirname(__file__), '..\\unittests'),
                       three=(['c:\\does_not_exist', '..\\unittests\\does_not_exist'],))

    def test_command_line(self):
        pass


class TestDescriptorConfig(unittest.TestCase):
    @classmethod
    def illegal(cls, kwargs):
        return False

    def test_not_many_and_no_types(self):
        for kwargs in dict_product(type=int, many=False, default=(MISSING, None, 0, 1), valid=(lambda v: v < 10, None)):
            if not self.illegal(kwargs):
                class Parser(CmdParser):
                    arg = Argument(**kwargs)
            else:
                with self.assertRaises(ConfigError):
                    class Parser(CmdParser):
                        arg = Argument(**kwargs)

    def test_many_and_no_types(self):
        for kwargs in dict_product(type=int, many=True, default=(MISSING, None, [0, 1], [2, 3]),
                                   valid=(lambda v: len(v) < 10, None)):
            if not self.illegal(kwargs):
                class Parser(CmdParser):
                    arg = Argument(**kwargs)
            else:
                with self.assertRaises(ConfigError):
                    class Parser(CmdParser):
                        arg = Argument(**kwargs)

    def test_not_many_and_types(self):
        type_values = {bool: (False, True),
                       int: (-1, 0, 1, 100),
                       float: (-1.0, 0.0, 1.0, float('inf')),
                       str: ('', 'a', ' a ab b  ', '\n \t a\nb \t\n '),
                       datetime: (datetime(1999, 1, 2, 3, 4, 5),),
                       timedelta: (timedelta(seconds=1000),),
                       date: (date(1999, 3, 4),),
                       time: (time(22, 4, 5),)}

        for type, values in type_values.items():
            for kwargs in dict_product(type=type, many=False, default=(MISSING, None) + values,
                                       valid=(lambda v: v <= max(values), None)):
                if not self.illegal(kwargs):
                    class Parser(CmdParser):
                        arg = Argument(**kwargs)
                else:
                    with self.assertRaises(ConfigError):
                        class Parser(CmdParser):
                            arg = Argument(**kwargs)

    def test_many_and_types(self):
        type_values = {bool: (False, True),
                       int: (-1, 0, 1, 100),
                       float: (-1.0, 0.0, 1.0, float('inf')),
                       str: ('', 'a', ' a ab b  ', '\n \t a\nb \t\n '),
                       datetime: (datetime(1999, 1, 2, 3, 4, 5),),
                       timedelta: (timedelta(seconds=1000),),
                       date: (date(1999, 3, 4),),
                       time: (time(22, 4, 5),)}

        for type, values in type_values.items():
            for kwargs in dict_product(type=type, many=True, default=(MISSING, None, values),
                                       valid=(lambda v: len(v) == len(values), None)):
                if not self.illegal(kwargs):
                    class Parser(CmdParser):
                        arg = Argument(**kwargs)
                else:
                    with self.assertRaises(ConfigError):
                        class Parser(CmdParser):
                            arg = Argument(**kwargs)

    def test_validation(self):
        """ very basic but a lot of combinations, mainly aiming for default validation """
        type_values = {bool: (False, True, []),
                       int: (-1, 0, 1, 100, []),
                       float: (-1.0, 0.0, 1.0, float('inf'), []),
                       str: ('', 'a', ' ab ', ' a ab b  ', '\n \t a\nb \t\n ', []),
                       datetime: (datetime(1999, 1, 2, 3, 4, 5), []),
                       timedelta: (timedelta(seconds=1000), []),
                       date: (date(1999, 3, 4), []),
                       time: (time(22, 4, 5), [])}

        for type, values in type_values.items():
            for kwargs in dict_product(type=type, many=False, default=values, valid=lambda v: v < min(values)):
                with self.assertRaises(ConfigError):
                    class Parser(CmdParser):
                        arg = Argument(**kwargs)

        for type, values in type_values.items():
            for kwargs in dict_product(type=type, many=True, default=[values], valid=lambda v: len(v) < 0):
                with self.assertRaises(ConfigError):
                    class Parser(CmdParser):
                        arg = Argument(**kwargs)
