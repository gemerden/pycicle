import itertools

long_line = 120 * chr(8254)
short_line = 80 * chr(8254)


class BaseString(object):
    template = None

    def __call__(self, *args, **kwargs):
        raise NotImplementedError


class Document(BaseString):
    template = "\n{title}\n{separator}\n{intro}\n\n{chapters}\n"

    def __init__(self, title, intro, chapters):
        self.title = title
        self.intro = intro
        self.chapters = chapters

    def __call__(self, start="   ", separator=long_line):
        document = self.template.format(
            title=self.title,
            separator=separator,
            intro=self.intro,
            chapters="\n".join(self.chapters),
        )
        return "\n".join(start + line for line in document.split("\n"))


class Chapter(BaseString):
    template = "{name}\n{separator}\n{content}\n"

    def __init__(self, name, content):
        self.name = name
        self.content = content

    def __call__(self, separator=long_line):
        if self.content == "":
            return ""
        return self.template.format(
            name=self.name, separator=separator, content=self.content
        )


class ItemList(BaseString):
    template = "{intro}:\n{items}\n"

    def __init__(self, intro="", items=(), extra=""):
        self.intro = intro
        self.items = items
        self.extra = extra

    def _item_strings(self, bullets):
        if isinstance(
            self.items, dict
        ):  # filter out empties before to not have gaps in numbered bullets
            items = [(k, it) for k, it in self.items.items() if it != ""]
        else:
            items = [it for it in self.items if it != ""]

        if isinstance(self.items, dict):
            return [f" {b} {k}:\t{it}" for b, (k, it) in zip(bullets, items)]
        return [f" {b} {it}" for b, it in zip(bullets, items)]

    def __call__(self, start=1):
        if isinstance(start, str):
            bullets = itertools.repeat(start)
        else:
            bullets = itertools.count(start)

        item_list = "\n".join(self._item_strings(bullets))
        if self.intro:
            item_list = self.template.format(intro=self.intro, items=item_list)
        if self.extra:
            item_list = item_list + f"\n{self.extra}\n"
        return item_list
