from pathlib import Path


class FileFolderBase(str):
    exists = False
    does_exist = None

    def __new__(cls, string=''):
        if not string or (isinstance(string, str) and not string.strip()):
            return super().__new__(cls)
        if ',' in string:
            raise ValueError(f"file or folder '{string}' contains a ','")
        path = Path(string)
        if cls.exists and not cls.does_exist(path):
            raise ValueError(f"file: {str(path)} does not exist")
        return super().__new__(cls, path)


class FileBase(FileFolderBase):
    extensions = ()
    does_exist = Path.is_file

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        extensions = set()
        for ext in cls.extensions:
            ext = ext.strip()
            if ext.startswith('.'):
                ext = ext[1:]
            extensions.add(ext)
        cls.extensions = frozenset(extensions)

    def __new__(cls, string=''):
        _, _, ext = string.rpartition('.')
        if cls.extensions and ext not in cls.extensions:
            raise ValueError(f"incorrect extension for file: {string}")
        return super().__new__(cls, string)


class FolderBase(FileFolderBase):
    does_exist = Path.is_dir


def File(*extensions, exists=False):
    return type('File', (FileBase,), dict(exists=exists, extensions=extensions))


def Folder(exists=False):
    return type('Folder', (FolderBase,), dict(exists=exists))


class ChoiceBase(object):
    choices = ()

    def __new__(cls, value=None):
        if value is None:
            value = cls.choices[0]
        elif isinstance(value, str):
            value = cls.__bases__[1](value)
        if value not in cls.choices:
            raise ValueError(f"value '{str(value)}' is not a choice in {cls.choices}")
        return super().__new__(cls, value)


def Choice(*choices):
    """ note that the class of the choices becomes a base class"""
    if not len(choices):
        raise ValueError(f"cannot define Choice without choices")
    if any(type(c) is not type(choices[0]) for c in choices):
        raise ValueError(f"all choices must be of same class")
    return type('Choice', (ChoiceBase, type(choices[0])), {'choices': choices})


if __name__ == '__main__':
    file = File('.txt')
    f = file('sample.txt')
    print(isinstance(f, file))

    choice = Choice('a', 'b', 'c')
    c = choice('b')
    print(c, isinstance(c, choice))
    c = choice('d')
