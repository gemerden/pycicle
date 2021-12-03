# sayit.py
from pycicle import CmdParser, Argument


def say_it(name, texts):
    start = '\n\t'  # cannot use '\' in f-strings
    print(f"{name} says: {start}{start.join(texts)}")


class Sayer(CmdParser):
    name = Argument(str, default='Bob')
    texts = Argument(str, many=True, default=['nothing'])


if __name__ == '__main__':
    sayer = Sayer(say_it)
    sayer.parse('Ann -t Hello Goodbye', run=True)