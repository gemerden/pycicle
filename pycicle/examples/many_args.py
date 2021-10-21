from pycicle import CmdParser, Argument
from pycicle.basetypes import File, Choice
from pycicle.tools.utils import MISSING
from pycicle.unittests.testing_tools import dict_product

if __name__ == '__main__':
    from datetime import time


    class Parser(CmdParser):
        """
        this is the help text for the parser:
         - help
         - more help
        """
        one_int_no_default = Argument(int, help='helpful?')
        one_int_default = Argument(int, default=1, help='helpful?')
        more_int_no_default = Argument(int, many=True, help='helpful?')
        more_int_default = Argument(int, many=True, default=[1, 1], help='helpful?')
        one_int_no_default_valid = Argument(int, valid=lambda v: 0 < v <= 10, help='helpful?')
        one_int_default_valid = Argument(int, default=1, valid=lambda v: 0 < v <= 10, help='helpful?')
        more_int_no_default_valid = Argument(int, many=True, valid=lambda v: all(i > 0 for i in v), help='helpful?')
        more_int_default_valid = Argument(int, many=True, default=[1, 1], valid=lambda v: all(i > 0 for i in v), help='helpful?')


    def printer(**kwargs):
        print(f"printer: {kwargs}")


    Parser.gui(target=printer)
