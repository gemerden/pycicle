from pycicle import ArgParser, Argument


class Parser(ArgParser):
    aaa = Argument(str)
    bbb = Argument(str)


if __name__ == '__main__':
    def run(aaa, bbb):
        print(f"aaa = {aaa}, bbb = {bbb}")
    Parser(target=run)
