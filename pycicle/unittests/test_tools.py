import unittest

from pycicle.tools.parsers import parse_split, split_encode


class TestTools(unittest.TestCase):
    def test_parse_split(self):
        good_strings = ['', 'a', 'a b c', 'a "b c" d', 'a "b " d', 'a "b " d', 'a "" b', '""', '" "']
        diff_strings = ['  ', 'a', ' a', ' a  ', 'a b', 'a "b c" d ', 'a "b" c', 'a  ""  b', '"" ']  # still OK
        evil_strings = ['"', '"""', 'a" b', ' a " b""', '"'"'"'']

        for string in good_strings:
            decoded = parse_split(string)
            recoded = split_encode(decoded)
            assert string == recoded

        for string in diff_strings:
            recoded = split_encode(parse_split(string))
            decoded = parse_split(recoded)
            rerecoded = split_encode(decoded)
            assert rerecoded == recoded

        for string in evil_strings:
            with self.assertRaises(ValueError):
                parse_split(string)



