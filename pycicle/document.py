import itertools

underline = 120 * chr(8254)


class BaseString(object):
    template = None

    def __call__(self, *args, **kwargs):
        raise NotImplementedError


class Document(BaseString):
    template = "\n{title}\n{line}\n{intro}\n\n{chapters}\n"

    def __init__(self, title, intro, chapters):
        self.title = title
        self.intro = intro
        self.chapters = chapters

    def __call__(self, start='   ', line=underline):
        document = self.template.format(title=self.title,
                                        line=line,
                                        intro=self.intro,
                                        chapters='\n'.join(self.chapters))
        return '\n'.join(start + line for line in document.split('\n'))


class Chapter(BaseString):
    template = "{name}\n{line}\n{content}\n"

    def __init__(self, name, content):
        self.name = name
        self.content = content

    def __call__(self, line=underline):
        if self.content == '':
            return ''
        return self.template.format(name=self.name, line=line, content=self.content)


class ItemList(BaseString):
    template = "{intro}:\n{items}\n"

    def __init__(self, intro='', items=(), extra=''):
        self.intro = intro
        self.items = items
        self.extra = extra

    def _item_strings(self, bullets):
        if isinstance(self.items, dict):
            return [f" {b} {k}:\t{it}" for b, (k, it) in zip(bullets, self.items.items()) if it != '']
        return [f" {b} {it}" for b, it in zip(bullets, self.items) if it != '']

    def __call__(self, start=1):
        if isinstance(start, str):
            bullets = itertools.repeat(start)
        else:
            bullets = itertools.count(start)

        item_list = '\n'.join(self._item_strings(bullets))
        if self.intro:
            item_list = self.template.format(intro=self.intro,
                                             items=item_list)
        if self.extra:
            item_list = item_list + f"\n{self.extra}\n"
        return item_list
