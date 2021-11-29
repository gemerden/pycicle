from pycicle import CmdParser


def func(name: str, messages: list[str] = ('Hello',)):
    for m in messages:
        print(f"{name} says '{m}'")

parser = CmdParser.from_callable(func)
parser('-n Bob -m hello goodbye')