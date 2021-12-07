from typing import List

from pycicle import CmdParser

def talk(name: str, messages: List[str] = ('Hello',)):
    for m in messages:
        print(f"{name} says '{m}'")


if __name__ == '__main__':
    CmdParser.from_callable(talk).gui()
