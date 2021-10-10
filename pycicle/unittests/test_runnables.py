import unittest
import subprocess


class TestArgParser(unittest.TestCase):

    def test_basic(self):
        subprocess.run(['python', __file__+'/../runnables/basic.py', '-a', 'abc', '-b', 'cde'])

