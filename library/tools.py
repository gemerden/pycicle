class Missing(object):
    def __bool__(self):
        return False

    def __str__(self):
        return "MISSING"

    __repr__ = __str__


MISSING = Missing()
