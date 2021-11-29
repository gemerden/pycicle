from pycicle import CmdParser, Argument


class Parser(CmdParser):
    aaa = Argument(str)
    bbb = Argument(str)


if __name__ == '__main__':
    def run(aaa, bbb):
        print(f"aaa = {aaa}, bbb = {bbb}")
    Parser(run)()
