from clapy import ArgParser, Argument, File


def is_valid_host(ip):
    """ roughly """
    parts = list(map(int, ip.split('.')))
    return all(0 <= p < 256 for p in parts)


def is_valid_port(port):
    return 10 <= int(port) <= 9999


class StartServerParser(ArgParser):
    """
    this is the help text for the parser:
     - help
     - more help
    """

    host = Argument(str, required=True, valid=is_valid_host,
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
    def start_server(host, port, restart, debug, logfile=None):
        print(f"starting server on: {host}:{port} with restart: {restart}, debug: {debug} and logfile: {logfile}")


    StartServerParser(target=start_server)
