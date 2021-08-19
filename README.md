# PyCicle
 A simplified argument parser for starting python programs from the command line. A Gui generator to start the same program from a Window.

## Purpose

This module has 2 main purposes:

1. Simplify the configuration of command line interfaces for your program*,
2. Let users of your script start the program from a GUI instead of the command line.

*compared to using `argparse` or `optparse` from the standard library.

## Installation

PyCicle can be easily installed with pip installed with `pip install pycicle`.

## Example

To start a server you can configure the parser as follows:

```python
# file: run_server.py
from somewhere import Server  # some webserver
from pycicle import ArgParser, Argument, File, Choice

def is_valid_host(ip):
    """ roughly """
    parts = list(map(int, ip.split('.')))
    return all(0 <= p < 256 for p in parts)

def is_valid_port(port):
    return 10 <= int(port) <= 9999

class StartServer(ArgParser):
    """
    this is the help text for the parser
    """
    proto = Argument(Choice('http', 'https'), required=True, default='http',
                     help='the protocol the server will use')
    host = Argument(str, required=True, default='0.0.0.0', valid=is_valid_host,
                    help='host IP of the server')
    port = Argument(str, required=True, valid=is_valid_port, default=8080,
                    help='port on which the server should run')
    restart = Argument(bool, default=True, required=True,
                       help='should the server restart after crash?')
    debug = Argument(bool, default=False, required=True,
                     help='run in debug mode')
    logfile = Argument(File('.log'), required=False, default=None,
                       help='logfile for the server, log to stdout if absent')

if __name__ == '__main__':
    def start_server(proto, host, port, restart, debug, logfile=None):
        Server(proto=proto, host=host, port=port, log=logfile).run_forever(restart=restart, debug=debug)

    StartServer(target=start_server)
```

Running this file from the command line with arguments in the usual style ( e.g. `python run_server.py -p 80`)  will work as normal: it will call `start_server` with the provided arguments. Just calling  `python run_server.py` however will open a window like this:

![window](pycicle/images/window.PNG)



Allowing the user to configure the server with help and validation, run the server or copy the resulting command line to a command prompt. 
