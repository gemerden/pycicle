from clapy import ArgParser, Argument
from basetypes import File, Choice

if __name__ == '__main__':
    from datetime import time


    class Parser(ArgParser):
        """
        this is the help text for the parser:
         - help
         - more help
        """
        pos = Argument(float, positional=True, help='Is this helping?')
        const = Argument(int, constant=True, default=11)
        default = Argument(int, default=1)
        required = Argument(str, required=True, default='yeah')
        valid = Argument(int, valid=lambda v: v < 10)
        bool = Argument(bool)
        many = Argument(int, many=True)
        time = Argument(time)
        file = Argument(File('.json'), many=True)
        choice = Argument(Choice("apple", "pear", "orange"))


    def printer(**kwargs):
        print(f"printer: {kwargs}")


    Parser(target=printer)
