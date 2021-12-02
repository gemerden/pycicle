from typing import List

import sys

sys.path.append('D:/documents/_Code_/_repos_/pycicle')
from pycicle import CmdParser


def concatenate(strings: List[str], sep: str):
    print(sep.join(strings))


if __name__ == '__main__':
    CmdParser.from_callable(concatenate)('--gui')
