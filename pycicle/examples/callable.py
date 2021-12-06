from pycicle import CmdParser

def talk(name: str, messages: list[str] = ('Hello',)):
    for m in messages:
        print(f"{name} says '{m}'")


if __name__ == '__main__':
    CmdParser.from_callable(talk).gui()
