from pycicle.tools import MISSING


def parse(cmd_line, arguments):

    def create_lookups(arguments):
        arg_lookup, kwarg_lookup = {}, {}
        for argument in arguments:
            if len(argument.flags):
                for flag in argument.flags:
                    kwarg_lookup[flag] = argument
            else:
                arg_lookup[argument.name] = argument
        return arg_lookup, kwarg_lookup

    arg_lookup, kwarg_lookup = create_lookups(arguments)

    def split(cmd_line):
        if isinstance(cmd_line, str):
            cmd_line = [s.strip() for s in cmd_line.split()]

        for i in range(len(cmd_line)):
            if cmd_line[i] in kwarg_lookup:
                return cmd_line[:i], cmd_line[i:]
        return cmd_line[:], []

    def parse_args(arg_list):
        parsed_args = {}
        for name, argument in arg_lookup.items():
            if argument.many is False:
                parsed_args[name] = argument.decode(arg_list.pop(0))
            elif argument.many is True:
                parsed_args[name] = argument.decode(arg_list)
                del arg_list[:]
            else:  # many is integer
                parsed_args[name] = argument.decode(arg_list[:argument.many])
                del arg_list[:argument.many]

        if len(arg_list):
            raise ValueError(f"illegal number of positional arguments found")

        return parsed_args

    def parse_kwargs(kwarg_list):
        parse_dict = {}
        last_flag = None
        for string in kwarg_list:
            if string in kwarg_lookup:
                last_flag = string
                parse_dict[last_flag] = []
            else:
                parse_dict[last_flag].append(string)

        parsed_kwargs = {}
        for flag, strings in parse_dict.items():
            argument = kwarg_lookup[flag]
            if argument.novalue is not MISSING:
                if not len(strings):
                    parsed_kwargs[argument.name] = argument.novalue
                    continue
            if argument.many is False:
                parsed_kwargs[argument.name] = argument.decode(strings[0])
            else:
                parsed_kwargs[argument.name] = argument.decode(strings)

        return parsed_kwargs

    args, kwargs = split(cmd_line)
    parsed = parse_args(args)
    parsed.update(parse_kwargs(kwargs))
    return parsed
