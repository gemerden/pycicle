import unittest

from pycicle import Argument, ArgParser
from pycicle import cmd_parser


class TestParser(unittest.TestCase):

    def test_kwarg(self):
        class Parser(ArgParser):
            arg = Argument(str)

        parsed = cmd_parser.parse('-a abc', Parser._arguments)
        assert len(parsed) == 1
        assert parsed['arg'] == 'abc'

    def test_multiple_kwargs(self):
        class Parser(ArgParser):
            a = Argument(str)
            b = Argument(str)

        parsed = cmd_parser.parse('-a abc -b cde', Parser._arguments)
        assert len(parsed) == 2
        assert parsed['a'] == 'abc'
        assert parsed['b'] == 'cde'

    def test_many_kwarg(self):
        class Parser(ArgParser):
            arg = Argument(str, many=True)

        parsed = cmd_parser.parse('-a abc cde', Parser._arguments)
        assert len(parsed) == 1
        assert parsed['arg'] == ['abc', 'cde']

    def test_fixed_number_kwarg(self):
        class Parser(ArgParser):
            arg = Argument(str, many=3)

        parsed = cmd_parser.parse('-a abc cde efg', Parser._arguments)
        assert len(parsed) == 1
        assert parsed['arg'] == ['abc', 'cde', 'efg']

    def test_positional(self):
        class Parser(ArgParser):
            arg = Argument(str, positional=True)

        parsed = cmd_parser.parse('abc', Parser._arguments)
        assert len(parsed) == 1
        assert parsed['arg'] == 'abc'

    def test_many_positional(self):
        class Parser(ArgParser):
            arg = Argument(str, many=True, positional=True)

        parsed = cmd_parser.parse('abc cde', Parser._arguments)
        assert len(parsed) == 1
        assert parsed['arg'] == ['abc', 'cde']

    def test_multiple_positionals(self):
        class Parser(ArgParser):
            a = Argument(str, positional=True)
            b = Argument(str, positional=True)

        parsed = cmd_parser.parse('abc cde', Parser._arguments)
        assert len(parsed) == 2
        assert parsed['a'] == 'abc'
        assert parsed['b'] == 'cde'

    def test_multiple_positionals_with_many(self):
        class Parser(ArgParser):
            a = Argument(str, positional=True)
            b = Argument(str, many=2, positional=True)
            c = Argument(str, many=True, positional=True)

        parsed = cmd_parser.parse('abc cde efg ghi ijk', Parser._arguments)
        assert len(parsed) == 3
        assert parsed['a'] == 'abc'
        assert parsed['b'] == ['cde', 'efg']
        assert parsed['c'] == ['ghi', 'ijk']

    def test_mixed(self):
        class Parser(ArgParser):
            a = Argument(str, positional=True)
            b = Argument(str)

        parsed = cmd_parser.parse('abc -b cde', Parser._arguments)
        assert len(parsed) == 2
        assert parsed['a'] == 'abc'
        assert parsed['b'] == 'cde'

    def test_negative_integer(self):  #uses dash: '-'
        class Parser(ArgParser):
            a = Argument(int, positional=True)
            b = Argument(int)

        parsed = cmd_parser.parse('-1 -b -2', Parser._arguments)
        assert len(parsed) == 2
        assert parsed['a'] == -1
        assert parsed['b'] == -2

    def test_novalue(self):
        class Parser(ArgParser):
            a = Argument(str, novalue='x')
            b = Argument(str, novalue='x')
            c = Argument(str, novalue='x')

        parsed = cmd_parser.parse('-a -b yes -c', Parser._arguments)
        assert len(parsed) == 3
        assert parsed['a'] == 'x'
        assert parsed['b'] == 'yes'
        assert parsed['c'] == 'x'

