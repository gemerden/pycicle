from pathlib import Path


class FileFolderBase(str):
    existing = False  # indicates whether file or folder is expected to exist
    does_exist = None  # function to test for existence, implemented in subclasses

    @classmethod
    def string(cls, short=False):
        raise NotImplementedError

    def __new__(cls, string=''):
        if not string or (isinstance(string, str) and not string.strip()):
            return super().__new__(cls)
        if ',' in string:
            raise ValueError(f"file or folder '{string}' contains a ','")
        path = Path(string)
        if cls.existing and not cls.does_exist(path):
            raise ValueError(f"file: {str(path)} does not exist")
        return super().__new__(cls, path)


class FileBase(FileFolderBase):
    extensions = ()  # allowed file extensions
    does_exist = Path.is_file

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        extensions = set()
        for ext in cls.extensions:
            ext = ext.strip()
            if ext.startswith('.'):
                ext = ext[1:]
            extensions.add(ext)
        cls.extensions = tuple(extensions)

    @classmethod
    def string(cls, short=False):
        if short:
            return cls.__name__
        if cls.extensions:
            return f"File({', '.join(cls.extensions)}, existing={cls.existing})"
        return f"File(existing={cls.existing})"

    def __new__(cls, string=''):
        _, _, ext = string.rpartition('.')
        if cls.extensions and ext not in cls.extensions:
            raise ValueError(f"incorrect extension for file: {string}; should be one of {cls.extensions}")
        return super().__new__(cls, string)


class FolderBase(FileFolderBase):
    does_exist = Path.is_dir

    @classmethod
    def string(cls, short=False):
        if short:
            return cls.__name__
        return f"Folder(existing={cls.existing})"


def File(*extensions, existing=False):
    return type('File', (FileBase,), dict(existing=existing, extensions=extensions))


def Folder(existing=False):
    return type('Folder', (FolderBase,), dict(existing=existing))


class ChoiceBase(object):
    choices = ()  # defined in def Choice() below

    @classmethod
    def string(cls, short=False):
        if short:
            return ' | '.join(map(str, cls.choices))
        return f"Choice({' | '.join(map(str, cls.choices))})"

    def __new__(cls, value=None):
        if value is None:
            value = cls.choices[0]
        elif isinstance(value, str):
            value = cls.__bases__[1](value)  # convert to second baseclass == type of choices
        if value not in cls.choices:
            raise ValueError(f"value '{str(value)}' is not a choice in {cls.choices}")
        return super().__new__(cls, value)


def Choice(*choices):
    """ note that the class of the choices becomes a base class, e.g. issubclass(Choice(1,2,3), int) == True """
    if not len(choices):
        raise ValueError(f"cannot define Choice without any choices")
    if any(type(c) is not type(choices[0]) for c in choices):
        raise ValueError(f"all choices must be of same type")
    return type('Choice', (ChoiceBase, type(choices[0])), {'choices': choices})


def get_type_string(type, short=False):
    try:
        return type.string(short)
    except AttributeError:
        return type.__name__ if short else type.__qualname__


if __name__ == '__main__':
    file = File('.txt')
    f = file('sample.txt')
    print(isinstance(f, file))

    choice = Choice('a', 'b', 'c')
    c = choice('b')
    print(c, isinstance(c, choice))
    c = choice('d')
