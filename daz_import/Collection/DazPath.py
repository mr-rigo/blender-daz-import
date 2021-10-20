import os
from sys import platform
from urllib.parse import unquote, quote


class DazPath:
    unquote = unquote

    @classmethod
    def normalize(cls, id: str) -> str:
        ref = cls.lower_path(cls.undo_quote(quote(id)))
        return ref.replace("//", "/")

    @classmethod
    def lower_path(cls, path: str) -> str:
        # return path
        if len(path) > 0 and path[0] == "/":
            words = path.split("#", 1)
            if len(words) == 1:
                return cls.lower(words[0])
            else:
                return cls.lower(words[0]) + "#" + words[1]
        else:
            return path

    @staticmethod
    def undo_quote(ref: str) -> str:
        ref = ref.replace("%23", "#").replace("%25", "%").replace(
            "%2D", "-").replace("%2E", ".").replace("%2F", "/").replace("%3F", "?")
        return ref.replace("%5C", "/").replace("%5F", "_").replace("%7C", "|")

    @staticmethod
    def lower(url: str) -> str:
        if platform == 'win32':
            url = url.lower()
        return url

    @classmethod
    def id(cls, id0: str, fileref: str) -> str:
        id = cls.normalize(id0)

        if len(id) == 0:
            print("Asset with no id in %s" % fileref)
            return fileref + "#"
        elif id[0] == "/":
            return id
        else:
            return fileref + "#" + id

    @classmethod
    def ref(cls, id: str, fileref: str) -> str:
        id = cls.normalize(id)

        if id[0] == "#":
            return fileref + id
        else:
            return id

    @staticmethod
    def path_fix(path: str):
        filepath = os.path.expanduser(path).replace("\\", "/")
        return filepath.rstrip("/ ")
