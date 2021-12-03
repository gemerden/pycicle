from pycicle import CmdParser

def talk(name: str, messages: list[str] = ('Hello',)):
    for m in messages:
        print(f"{name} says '{m}'")

CmdParser.from_callable(talk).gui()
