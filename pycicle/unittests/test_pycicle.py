import os
import unittest
from datetime import datetime, timedelta, date, time
from typing import List

from pycicle import CmdParser, Argument
from pycicle import File, Folder, Choice
from pycicle.exceptions import ConfigError
from pycicle.tools.utils import MISSING
from pycicle.unittests.testing_tools import dict_product, make_test_command, args_asserter, assert_product


class TestArgParser(unittest.TestCase):

    def test_basic(self):
        class Parser(CmdParser):
            pass

        Parser().parse('--help')
        import subprocess
        subprocess.run(['python', __file__, "--help"])

    def test_target(self):
        """ test whether target gets called """
        result = {}

        def target(**kwargs):
            result.update(kwargs)

        class Parser(CmdParser):
            arg = Argument(int)

        Parser(target)('--arg 1')
        assert result == {'arg': 1}

    def test_basic_keywords(self):

        class Parser(CmdParser):
            default = Argument(int, default=0)
            valid = Argument(int, valid=lambda v: v < 10)
            many = Argument(int, many=True)

        asserter = args_asserter(default=0, valid=4, many=[1, 2])

        parser = Parser(asserter).parse('-v 4 -m "1" 2')

        for kwargs in dict_product(default=(-1, 0, 1), valid=(-1, 0, 1), many=([9, 11],)):
            asserter = args_asserter(**kwargs)

            cmd = make_test_command(Parser, kwargs)
            parser = Parser(asserter).parse(cmd)
            assert parser.command(short=False) == cmd
            assert parser.command(short=True) == make_test_command(Parser, kwargs, short=True)

    def test_flags(self):

        class Parser(CmdParser):
            default = Argument(int, default=0)
            valid = Argument(int, valid=lambda v: v < 10)
            many = Argument(int, many=True)

        asserter = args_asserter(default=0, valid=4, many=[1, 2])

        parser = Parser(asserter).parse('-v 4 -m "1" 2')

        for kwargs in dict_product(default=(-1, 0, 1), valid=(-1, 0, 1), many=([9, 11],)):
            asserter = args_asserter(**kwargs)

            cmd = make_test_command(Parser, kwargs)
            parser = Parser(asserter).parse(cmd)
            assert parser.command(short=False) == cmd
            assert parser.command(short=True) == make_test_command(Parser, kwargs, short=True)

    def test_positionals(self):
        class Parser(CmdParser):
            a = Argument(int, many=True)

        def target(**kwargs):
            assert kwargs == dict(a=[1, 2, 3, 4])

        Parser(target).parse('1 2 3 4')

        class Parser(CmdParser):
            a = Argument(int, many=False)
            b = Argument(int, many=True)
            c = Argument(int, many=False)

        def target(**kwargs):
            assert kwargs == dict(a=1, b=[2, 3], c=4)

        Parser(target).parse('1 2 3 4')

        class Parser(CmdParser):
            b = Argument(int, many=True)
            c = Argument(int, many=True)

        with self.assertRaises(ValueError):
            Parser(target).parse('1 2')

        class Parser(CmdParser):
            a = Argument(int, many=False)
            b = Argument(int, many=True)
            c = Argument(int, many=True)
            d = Argument(int, many=False)

        with self.assertRaises(ValueError):
            Parser(target).parse('1 2 3 4, 5')

    def test_required(self):
        class Parser(CmdParser):
            a = Argument(int)
            b = Argument(int, default=0)

        Parser().parse('-a 1')

        with self.assertRaises(ValueError):
            Parser().parse('-b 1')  # no 'a'

    def test_valid(self):
        class Parser(CmdParser):
            units = Argument(int, valid=lambda v: v >= 0)
            name = Argument(str, valid=lambda v: len(v) >= 3)

        for kwargs in dict_product(units=range(-3, 3), name=('an', 'ann', 'anna')):
            asserter = args_asserter(**kwargs)
            cmd = make_test_command(Parser, kwargs)
            if kwargs['units'] < 0 or len(kwargs['name']) < 3:
                with self.assertRaises(ValueError):
                    Parser(asserter).parse(cmd)
            else:
                Parser(asserter).parse(cmd)

    def test_default(self):
        class Parser(CmdParser):
            name = Argument(str)
            units = Argument(int, default=3)

        parser = Parser().parse('-n bob')

        assert parser.keyword_arguments.name == 'bob'
        assert parser.keyword_arguments.units == 3

    def test_missing_value(self):
        class Parser(CmdParser):
            x = Argument(bool, default=False)
            y = Argument(bool, default=False)
            z = Argument(bool, default=None)

        parser = Parser().parse('-x')

        assert parser.keyword_arguments.x is True
        assert parser.keyword_arguments.y is False
        assert parser.keyword_arguments.z is None

        with self.assertRaises(ValueError):
            parser = Parser().parse('-z')

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
        parser = Parser(asserter).parse(test_cmd)
        assert test_cmd == parser.command()

        parser2 = Parser(asserter).parse()
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
        parser = Parser(asserter).parse()

    def test_choice(self):
        class Parser(CmdParser):
            one = Argument(Choice(1, 2, 3))
            two = Argument(Choice(1, 2, 3), many=True)

        assert_product(Parser, one=(1, 2), two=([1, 3], [2, 1]))

    def test_flags_config(self):
        class Parser(CmdParser):
            one = Argument(int, flags=('-x', '--xxx'))
            two = Argument(int, flags=('-y', '--yyy'))

        assert Parser.keyword_argument_class.one.flags == ('-x', '--xxx')
        assert Parser.keyword_argument_class.two.flags == ('-y', '--yyy')

        class Parser(CmdParser):
            one = Argument(int, flags=('-x', '--xxx'))
            two = Argument(int, flags=('-x', '--yyy'))

        assert Parser.keyword_argument_class.one.flags == ('-x', '--xxx')
        assert Parser.keyword_argument_class.two.flags == ('--yyy',)  # doubles removed

        with self.assertRaises(ConfigError):
            class Parser(CmdParser):
                one = Argument(int, flags=('-x', '--xxx'))
                two = Argument(int, flags=('-x',))  # double removed, no flags left

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

    def test_quotes(self):
        cmds = ['a', "b", '"c"', '"d e"',
                '-t a', "-t b", '-t "c"', '-t "d e"']

        def asserter(text):
            assert text in 'abc' or text == 'd e'

        class Parser(CmdParser):
            text = Argument(str)

        parser = Parser(asserter)

        parser('"d e"')

        for cmd in cmds:
            parser(cmd)

    def test_subparsers(self):
        class Ship:
            def __init__(self, name):
                self.name = name
                self.x = 0
                self.y = 0
                self.sunk = False

            def move(self, dx, dy):
                if not self.sunk:
                    self.x += dx
                    self.y += dy

            def sink(self, sunk):
                self.sunk = sunk

        class Move(CmdParser):
            dx = Argument(int)
            dy = Argument(int)

        class Sink(CmdParser):
            sunk = Argument(bool, default=True)

        class ShipCommand(CmdParser):
            name = Argument(str)

            def __init__(self):
                super().__init__(self.create,
                                 move=Move(self.move),
                                 sink=Sink(self.sink))
                self.ship = None

            def create(self, name):
                self.ship = Ship(name)

            def move(self, dx, dy):
                self.ship.move(dx, dy)

            def sink(self, sunk):
                self.ship.sink(sunk)

        ship_command = ShipCommand()
        ship_command('--name "Queen Mary"')
        assert ship_command.ship.name == "Queen Mary"
        ship_command('move 2 1')
        ship_command('move --dx -3 --dy -4')
        ship_command('move 4 5')
        assert ship_command.ship.x == 3
        assert ship_command.ship.y == 2
        ship_command('sink')
        assert ship_command.ship.sunk
        ship_command('move 4 5')  # sunk ships do not move
        assert ship_command.ship.x == 3
        assert ship_command.ship.y == 2

    def test_from_callable(self):
        output = []

        def func(name: str, messages: list[str] = ['Hello']):
            for message in messages:
                output.append((name, message))


        parser = CmdParser.from_callable(func)
        parser('Bob -m hello goodbye')
        assert output == [('Bob', 'hello'), ('Bob', 'goodbye')]


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
