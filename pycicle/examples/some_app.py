from pycicle import ArgParser, Argument
from pycicle.basetypes import File, Choice

if __name__ == '__main__':
    from datetime import time


    class Parser(ArgParser):
        """
        this is the help text for the parser:
         - help
         - more help
        """
        default = Argument(int, default=1, help='helpful?')
        valid = Argument(int, valid=lambda v: v < 10)
        bool = Argument(bool, default=False)
        many = Argument(int, many=True)
        time = Argument(time, default=None)
        file = Argument(File('.json'), many=True, default=[])
        choice = Argument(Choice("apple", "pear", "orange"), many=True, default=['pear'])
        switch = Argument(int, default=2, missing=3)


    def printer(**kwargs):
        print(f"printer: {kwargs}")


    Parser(target=printer, run_gui=True)
