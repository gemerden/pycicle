from argparse import ArgumentParser

MISSING = object()


class argument(object):
    def __init__(self, type, usekey=True, required=False, constant=False, default=MISSING, valid=None, action=None, help=""):
        self.name = None
        self.type = type
        self.usekey = usekey
        self.required = required
        self.constant = constant
        self.default = default
        self.valid = valid
        self.action = action
        self.help = help

    def __set_name__(self, cls, name):
        self.name = name

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        try:
            obj.__dict__[self.name]
        except KeyError:
            if self.default is not MISSING:
                return self.default
            raise AttributeError(f"missing argument '{self.name}'")

    def __set__(self, obj, value):
        value = self.type(value)
        if self.valid and not self.valid(value):
            raise ValueError(f"invalid argument '{self.name}'")
        if self.constant and self.name in obj.__dict__:
            raise AttributeError(f"constant argument '{self.name}' is already set")
        obj.__dict__[self.name] = value

    def _get_name_or_flag(self, arg_class) -> tuple:
        if self.usekey:
            if self.name[0] in arg_class.abbreviations:
                return '--' + self.name,
            return '--' + self.name, '-' + self.name[0]
        return self.name,

    def add(self, parser, arg_class):
        args = self._get_name_or_flag(arg_class)
        kwargs = dict(type=self.type,
                      required=self.required,
                      const=self.constant,
                      default=self.default,
                      action=self.action,
                      help=self.help)
        parser.add_argument(*args, **kwargs)


class ArgObject(object):
    parser_class = ArgumentParser
    arg_names = None  # set in __init_subclass__

    @classmethod
    def arguments(cls):
        for c in cls.__mro__:
            for name, arg in vars(c).items():
                if isinstance(arg, argument):
                    yield arg

    @classmethod
    def abbreviations(cls):
        """ used to prevent assigning short abbreviations (e.g. -f) twice """
        return set(arg.name[0] for arg in cls.arguments() if arg.usekey)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.parser = cls.parser_class(**kwargs)
        arguments = cls.arguments()
        for arg in arguments:
            arg.add(cls.parser, arg_class=cls)
        cls.arg_names = set(a.name for a in arguments)

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            if name not in self.__class__.arg_names:
                raise AttributeError(f"'{self.__class__.__name__}' has no argument '{name}'")
            setattr(self, name, value)


if __name__ == '__main__':
    class A:
        X = 0

    class B(A):
        Y = 1

    print('X' in vars(B))
    print('Y' in vars(B))
