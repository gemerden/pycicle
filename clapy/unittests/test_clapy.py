import unittest

from clapy import ArgParser, Argument


class TestArgParser(unittest.TestCase):

    def test_basic(self):
        class Parser(ArgParser):
            pass
        parser = Parser('-h')

    def test_basic_keywords(self):
        callback_target = []

        class Parser(ArgParser):
            pos = Argument(int, positional=True)
            const = Argument(int, constant=True)
            default = Argument(int, default=0)
            required = Argument(int, required=True)
            valid = Argument(int, valid=lambda v: v < 10)
            many = Argument(int, many=True)
            callback = Argument(int, callback=lambda v, n: callback_target.extend([v, n]))

        def assert_args(pos, const, default, required, valid, many, callback):
            assert pos == 1
            assert const == 2
            assert default == 0
            assert required == 3
            assert valid == 4
            assert many == [1, 2]
            assert callback == 5

        parser = Parser('1 -c 2 -r 3 -v 4 -m 1 2 --callback 5')
        parser.call(assert_args)
        assert callback_target[0] == 5


