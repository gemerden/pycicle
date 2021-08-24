# PyCicle
 A simplified argument parser for starting python programs from the command line. A GUI generator to start the same program from a Window.

## Purpose

This module has 2 main purposes:

1. Simplify the configuration of command line options for your program*,
2. Let users of your script start the program from a GUI instead of the command line.

*compared to using `argparse` or `optparse` from the standard library.

## Installation

PyCicle can be easily installed with pip installed with `pip install pycicle`.

## Example

To start a server you could configure the parser as follows:

```python
# file: start_server.py (in this example)
from somewhere import Server  # e.g. some webserver
from pycicle import ArgParser, Argument, File, Choice

def is_valid_host(ip):
    """ roughly """
    parts = list(map(int, ip.split('.')))
    return all(0 <= p < 256 for p in parts)

def is_valid_port(port):
    return 10 <= int(port) <= 9999

class StartServer(ArgParser):
    """
    This is the help text for the GUI. It shows when pressing the '?' button at the bottom.
    """
    proto = Argument(Choice('http', 'https'), required=True, default='http',
                     help='the protocol the server will use')
    host = Argument(str, required=True, default='0.0.0.0', valid=is_valid_host,
                    help='host IP of the server')
    port = Argument(str, required=True, valid=is_valid_port, default=8080,
                    help='port on which the server will run')
    restart = Argument(bool, default=True, required=True,
                       help='should the server restart after interruptions?')
    debug = Argument(bool, default=False, required=True,
                     help='run the server in debug mode')
    logfile = Argument(File('.log'), required=False, default=None,
                       help='logfile for the server, log to stdout if none')

if __name__ == '__main__':
    def start_server(proto, host, port, restart, debug, logfile=None):
        Server(proto=proto, host=host, port=port).run_forever(restart=restart, debug=debug, log=logfile)

    StartServer(target=start_server)
```

Running this file from the command line with arguments in the usual style, e.g. `> python start_server.py -p 80`)  will work as normal: it will call `start_server` with the provided arguments. Just calling  `> python start_server.py` however opens up a window:

![window](pycicle/images/window.PNG)



Allowing the user to configure the server with help and validation, run the server or copy the resulting command line to a command prompt. 

## Configuration

To configure the command line options (and corresponding GUI) an object oriented approach is used. When creating a new parser, you inherit from the base class `ArgParser` and define arguments with the descriptor `Argument` (more about descriptors [here](https://docs.python.org/3/howto/descriptor.html#descriptor-protocol)):

```python
# somefile.py
from pycicle import ArgParser, Argument

class MyParser(ArgParser):
    my_argument = Argument(int, help='my new command line argument')
```

From the command line the underlying program can be run with:

```
> python somefile.py --my_argument 3
```

or 

```
> python somefile.py -m 3
```



The easiest way to define the script to be started this way is to initialize the parser with a target:

```python
def printer(my_argument):
    print(my_argument)
    
parser = MyParser(target=printer)  # use the keyword 'target'
```



#### Configuring Argument

Arguments can be configured with a number of options. Only `type` is required:

- `type`: The type of the argument as used by the target. This can be `int, str, bool, float, datetime, date, time, timedelta`, but there are a few more (described below) and it is possible to create your own types,
- `required` (default=False): whether a value is required on the command line. If the `default` is `None` and no value for the argument is specified, this will raise an exception,
- `many` (default=False): whether one, a specific number or any number of values are expected, so:
  - `many=False` means there is a single value expected,
  - `many=True` means that any number of values is expected. They will be turned into a list,
  - `many=N` (with `N` a positive integer) means that there are exactly n values expected, resulting in a list, even if `N` is 1,
  - Note: the `type` above applies to the individual elements of the list,
- `default` (default=None): a default value for the argument. It must be of type `type` or `None` (the default for the default ;-). This value will be used if no other value is given on the command line,
- `positional` (default=False): whether the argument is positional, meaning it can be used without name or flag (e.g. no `-m` or `--my_argument` before the value),
- `valid` (default = None): an optional validator function for the argument value, allowing extra validation over the the typecheck based on `type`,
- `callback` (default=None): an optional callback that takes the value and the underlying namespace created by the parser as arguments and, for example, allows you to modify the namespace. This namespace will be used by the target as arguments,
- `help`: (default=""): last but not least, a help string that will be shown when the user types `> python somefile.py -h` (or `--help`) and is show in the GUI via the `? ` buttons.

Most inconsistencies between arguments will raise an exception, but some are impossible to track, like a `valid` function conflicting with the type.

A fully configured Argument could look like this (but the defaults should keep most configurations shorter ;-):

```python
class MyParser(ArgParser):
    my_argument = Argument(int, required=True, many=True, default=[1, 2, 3], positional=False, 		                                    valid=lambda v: v[0] == 1, callback=lambda v, ns: print(ns),
                           help='this is a pretty random argument')
```



#### Initializing the Parser

