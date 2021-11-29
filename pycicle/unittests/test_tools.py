import unittest

from pycicle.tools.parsers import quote_split, quote_join


class TestTools(unittest.TestCase):
    def test_parse_split(self):
        good_strings = ['', 'a', 'a b c', 'a "b c" d', 'a "b " d', 'a "b " d', 'a "" b', '""', '" "']
        diff_strings = ['  ', 'a', ' a', ' a  ', 'a b', 'a "b c" d ', 'a "b" c', 'a  ""  b', '"" ']  # still OK
        evil_strings = ['"', '"""', 'a" b', ' a " b""', '"'"'"'']

        for string in good_strings:
            decoded = quote_split(string)
            recoded = quote_join(decoded)
            assert string == recoded

        for string in diff_strings:
            recoded = quote_join(quote_split(string))
            decoded = quote_split(recoded)
            rerecoded = quote_join(decoded)
            assert rerecoded == recoded

        for string in evil_strings:
            with self.assertRaises(ValueError):
                quote_split(string)



