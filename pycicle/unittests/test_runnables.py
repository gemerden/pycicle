import unittest
import subprocess


class TestArgParser(unittest.TestCase):

    def run_command(self, file, cmd):
        p = subprocess.Popen(['python', __file__ + f'/../runnables/{file}', *cmd.split(' ')],
                             stdout=subprocess.PIPE)
        output, _ = p.communicate()
        return output.decode("utf-8")[:-2]  # remove '\r\n'

    def test_basic(self):
        output = self.run_command('basic.py', '-a abc -b cde')
        assert output == 'aaa = abc, bbb = cde'
