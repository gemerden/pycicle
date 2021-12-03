# PyCicle
 A simplified argument parser for starting python programs from the command line. A GUI generator to start the same program from a window.

## Purpose

This module has 2 main goals:

1. Make the configuration of command line options for your program easy*,
2. Allow users of your script to configure it from a GUI instead of the command line.

*compared to using `argparse` or `optparse` from the python standard library.

## Introduction

Using the well known python `argparse` library has always been somewhat of a chore. It is well known, it works and is stable, but not very intuitive to write and the resulting code is relatively hard to read. 

The first version of PyCicle was actually a thin wrapper around `argparse`, but when trying to implement more complicated command lines, the project stalled a bit ... That is why this project has its own parsing logic and follows the goals of a good command line interface, but there are some differences from the standard set by  `argparse`: in essence, the parsing logic used in PyCicle is very similar to the logic python itself uses to define and call functions. For example: positional arguments can be used on the command line as long as the parser can figure out how to assign them to the arguments defined in the parser.

## Features

PyCicle provides the following features:

- The ability to create a command line interface as a class with class attributes (descriptors), including:

  - *Validation*; type checking as well as custom validation are supported,
  - *Defaults*; if a default is configured for an argument, the argument can be omitted on the command line, conversely, if no default is configured, the arguments is required,
  - *Multiple values* for an argument; these will be parsed and result in a list of parsed values,
  - *Positional* arguments; as long as the parser can find the argument to assign the values to, flags can be omitted,
  - *Switches*; if the argument is of boolean type and the default is False, its flag can be omitted on the command line (meaning False) or be present without a value (meaning True),
  - *Subcommands*; a command line can be extended with subcommands; like `python server.py start -h 0.0.0.0 -p 5050`, where 'start' is the subcommand,
  - *Help*: a `help` text can be added to each argument and the doc-string of the parser class will be shown in the GUI or for the `--help` flag.

- From the definition of a command line interface, a GUI can be auto generated (for free, without any extra configuration), including:

  - A form (or forms) where the values for the command line can be set, with automatic validation,
  - The ability to start the underlying program with the configuration set in the form,
  - The ability to show (in different formats), save and load the command line,
  - The ability to select the configuration for different subcommands,
  - Help buttons for the command line as a whole as well as the individual arguments, partly auto-generated text, from the parser configuration.

- Some extras are available, like:

  - Running the command line as an interactive prompt, for example using subcommands to call different function in a single python session,

  - Creating a command line parser from an annotated function definition, like:

    ```python
    # talk.py
    from pycicle import CmdParser
    
    def talk(name: str, messages: list[str] = ('Hello',)):
        for message in messages:
            print(f"{name} says '{message}'")
    
    CmdParser.from_callable(talk).cmd()        
    ```

    with `> python talk.py --gui` shows:

    ![](pycicle/images/talk.PNG)

​				or could be called with e.g. `> python talk.py Bob -m Hello Goodbye`.

## Installation

PyCicle can be easily installed with pip using `pip install pycicle`.

## Example

To start a server you could configure the parser as follows:

```python
# file: start_server.py (in this example)
from pycicle import CmdParser, Argument, File, Choice

def is_valid_host(ip):
    """ roughly """
    parts = list(map(int, ip.split('.')))
    return len(parts) == 4 and all(0 <= p < 256 for p in parts)

def is_valid_port(port):
    return 10 <= int(port) <= 9999

class StartServer(CmdParser):
    """
    this part of is the help text for the parser
    """
    proto = Argument(Choice('http', 'https'), default='http', 
                     help='the protocol the server will use')
    host = Argument(str, default='0.0.0.0', valid=is_valid_host, 
                    help='host IP of the server')
    port = Argument(str, default=8080, valid=is_valid_port, 
                    help='port on which the server should run')
    restart = Argument(bool, default=True, 
                       help='should the server restart after exception?')
    logfile = Argument(File('.log'), default=None, 
                       help='logfile for the server, log to stdout if not set')
    debug = Argument(bool, default=False, help='run in debug mode')

if __name__ == '__main__':
    def start_the_server(proto, host, port, restart, debug, logfile=None):
        """ place holder function called from the parser """
        print(f"starting server: {proto}://{host}:{port} restart: {restart}, debug: {debug}, logfile: {logfile}")

    StartServer(start_the_server)()

```

Running this file from the command line with arguments in the usual style, e.g. `> python start_server.py -p 80`)  will work as usual: it will call `start_server` with the provided/default arguments. Calling  `> python start_server.py --gui` however opens up a window:

![window](pycicle/images/window.PNG)



Allowing the user to configure the server with help and validation, run the server or copy the resulting command line to a command prompt. 

## Configuration

To configure the command line options (and corresponding GUI) an object oriented approach is used. When creating a new parser, you inherit from the base class `CmdParser` and define arguments with the descriptor `Argument` (more about descriptors [here](https://docs.python.org/3/howto/descriptor.html#descriptor-protocol)):

```python
# prog.py
from pycicle import CmdParser, Argument

class MyParser(CmdParser):
    arg = Argument(int, help='my new command line argument')
```

From the command line the underlying program can be run with:

```
> python prog.py --arg 3
```

or with a short flag: 

```
> python prog.py -a 3
```

or with a positional argument (positional arguments are very much handled like positional arguments in python functions):

```
> python prog.py 3
```

The easiest way to define the script to be started this way is to initialize the parser with a target:

```python
def printer(arg):
    print(arg)
    
parser = MyParser(printer)
```

#### Configuring Arguments

Arguments can be configured with a number of options. Only `type` is required:

- `type`: The type of the argument as used by the target. This can be `int, str, bool, float, datetime, date, time, timedelta`, but there are a few more (described below) and it is possible to create your own types,
- `flags` (default=None): override the default flags; the default flags are `--[argument_name]` and `-[argument_name[0]]`,  so argument 'host' would have flags `--host` and `-h`,
- `many` (default=False): whether one or more values are expected, so:
  - `many=False` means there is a single value expected,
  - `many=True` means that any number of values is expected. They will be turned into a list,
  - Note: if `many=True` the `type` option above applies to the individual elements of the list,
- `default` (default=MISSING): a default value for the argument. It must be of type `type` or `None`. This value will be used if no value is given on the command line, MISSING means the argument is required on the command line,
- `valid` (default = None): an optional validator function (returning True or False) for the argument value, allowing extra validation over the the typecheck based on `type`.  `None` (the default) , means no extra validation will take place,
- `help`: (default=""): a help string that will be shown when the user types `> python somefile.py --help`) and is show in the GUI via the `? ` buttons.

Most inconsistencies between arguments will raise an exception, but some are impossible to track, like a `valid` function conflicting with the type. This will raise an exception when running the script itself though.

A fully configured Argument could look like this:

```python
class MyParser(CmdParser):
    some_arg = Argument(int, flags=('-a', '--arg'), many=True, default=[1, 2], valid=lambda v: len(v) == 2,
                           help='this is a pretty random argument')
```

#### Initializing the Parser

The parser constructor has one main argument and it is intended to be positional (to avoid name conflicts; see subparsers later on):

- `__target` (callable, default=None): the user callable to be called with the argument values set on the command line or in the GUI. Note that the target function parameters must be the same as the command line options! When no target is given, arguments are parsed (validated), but there is no target to run. Example:  `parser = Parser(some_target)`,

- `**subparsers`: additionally sub-parsers can be configured. These correspond to sub command on the command line. For example:

  ```python
  parser = MainParser(a_target,
                      init=InitParser(some_target),
                      run=RunParser(some_other_target))
  ```

  which from the command line would be called as `python file.py --name Bob` , `python file.py init --rank 3` or `python file.py run --time 30` (but with appropriate arguments).

Note that both a target and sub-parsers can be configured. More on sub-parsers below. 

#### Running the Parser

The are a couple of ways to run the parser (using `parser = Parser(some_target)` as example):

- `parser.cmd()`:  this can be called in a python file that will be run from the command line. The arguments to be parsed will be read from the command line (e.g. `> python start_server.py http 0.0.0.0 --port 8080`),
- `parser.gui()`: this will open the GUI when called. The GUI can be used to set the arguments and optionally run the program,
- `parser.parse(*cmds)`: can be used to specify individual command line arguments (usually in tests): for example `parser.parse('1', '2', '--text hello')`,
- `parser(cmd=None)`: A shortcut using the `Parser.__call__` method. If no arguments are given, this will run as `cmd()` above, otherwise it will parse the `cmd` and run the target (if a target is configured),
- To run the GUI from the command line, run `parser.cmd()` and argument `--gui`,  e.g.: `> python start_server.py --gui`,
- `parser.prompt()` will start prompt and an evaluation loop taking arguments from the command line, parsing them and executing a target function. This can be useful in combination with subparsers. 

#### Configuring Subparsers

Subparsers are parsers that can be called with an extra first argument on the command line. Both a main parser and subparsers can be used. An example:

```python
# ship.py
from pycicle import CmdParser, Argument

class Ship:
    def __init__(self, name):
        self.name = name
        self.x = 0
        self.y = 0
        self.sunk = False
        print(f"'{self.name}' was created")

    def move(self, dx, dy):
        if self.sunk:
            print(f"'{self.name}' sank, no more moving around")
        else:
            self.x += dx
            self.y += dy
            print(f"'{self.name}' moved to {self.x}, {self.y}")

    def sink(self, sunk):
        self.sunk = sunk
        print(f"'{self.name}' {'sank' if sunk else 'unsank'}")

class Move(CmdParser):
    dx = Argument(int)
    dy = Argument(int)

class Sink(CmdParser):
    sunk = Argument(bool, default=True)

class Quit(CmdParser):
    quit = Argument(bool, default=True)

class ShipCommand(CmdParser):
    name = Argument(str)

    def __init__(self):
        super().__init__(self.create,  # the target of the main parser
                         move=Move(self.move),  # self.move will be the target of sub-parser Move
                         sink=Sink(self.sink),
                         quit=Quit(self.quit))
        self.ship = None

    def create(self, name):  # called from the main parser
        self.ship = Ship(name)

    def move(self, dx, dy):  # called from sub-parser Move
        self.ship.move(dx, dy)

    def sink(self, sunk):
        self.ship.sink(sunk)

    def quit(self, quit):
        if quit:
            raise KeyboardInterrupt

if __name__ == '__main__':
    ship_command = ShipCommand()
    ship_command.prompt()
```

Note that how in `ShipCommand.__init__` the sub-parsers are added to the main parser and that the sub-parsers classes are also subclasses of `CmdParser`, meaning that sub_parsers can have sub-sub-parsers, and so on.

Apart from usage on a normal command line, sub-parsers can also be handy for interactive sessions. These can be started with a call to `parser.prompt()` as seen above. This would result in a session like:

```bash
$ python D:/documents/ship.py  #start the session
ship> "Queen Mary"  # or --name "Queen Mary"
'Queen Mary' was created
ship> move 2 3  # or move --dx 2 --dy 3
'Queen Mary' moved to 2, 3
ship> move -1 1
'Queen Mary' moved to 1, 4
ship> sink  # or sink 1 or sink sunk 1
'Queen Mary' sank
ship> quit

Process finished with exit code 0
```

When a sub-parser is configured, the GUI will give the option to select the sub-parser (subcommand) to configure and run:



![sub_window](pycicle/images/sub_window.png)



#### The Parser

