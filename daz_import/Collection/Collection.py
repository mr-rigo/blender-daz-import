import os
from typing import List, Any, Type, Dict
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Collection import DazPath
from sys import platform


class Collection:
    paths = []
    import_paths = []

    @classmethod
    def get_paths(cls):
        return Settings.contentDirs \
            + Settings.mdlDirs \
            + Settings.cloudDirs

    @classmethod
    def relative(cls, ref: str) -> str:
        path = DazPath.unquote(ref)

        for dazpath in cls.paths:
            n = len(dazpath)
            if path[0:n].lower() == dazpath.lower():
                return ref[n:]

        print("Not a relative path:\n  '%s'" % path)
        return ref

    @classmethod
    def update(cls) -> None:
        filepaths = []
        for path in cls.get_paths():
            if not path:
                continue

            if not os.path.exists(path):
                msg = ("The DAZ library path\n" +
                       "%s          \n" % path +
                       "does not exist. Check and correct the\n" +
                       "Paths to DAZ library section in the Settings panel." +
                       "For more details see\n" +
                       "http://diffeomorphic.blogspot.se/p/settings-panel_17.html.       ")

                raise ValueError(msg)
                # print(msg)
                # raise DazError(msg)
            else:
                filepaths.append(path)
                if not os.path.isdir(path):
                    continue
                for fname in os.listdir(path):
                    if "." not in fname:
                        numname = "".join(fname.split("_"))
                        if numname.isdigit():
                            subpath = "%s/%s" % (path, fname)
                            filepaths.append(subpath)

        cls.paths = filepaths

    @staticmethod
    def fix_path(path: str) -> str:
        """
        many asset file paths assume a case insensitive file system, try to fix here
        :param path:
        :return:
        """
        path_components = []
        head = path

        while True:
            head, tail = os.path.split(head)

            if tail != "":
                path_components.append(tail)
            else:
                if head != "":
                    path_components.append(head)
                path_components.reverse()
                break

        check = path_components[0]

        for pc in path_components[1:]:
            if not os.path.exists(check):
                return check

            cand = os.path.join(check, pc)

            if not os.path.exists(cand):
                corrected = [f for f in os.listdir(
                    check) if f.lower() == pc.lower()]
                if len(corrected) > 0:
                    cand = os.path.join(check, corrected[0])
                else:
                    msg = ("Broken path: '%s'\n" % path +
                           "  Folder: '%s'\n" % check +
                           "  File: '%s'\n" % pc +
                           "  Files: %s" % os.listdir(check))
                    print(msg)
                    # ErrorsStatic.report(msg, trigger=(4, 5))
            check = cand

        return check

    @classmethod
    def path(cls, ref: str, strict=True) -> str:

        def getExistingPath(filepath: str) -> str:
            if os.path.exists(filepath):
                return filepath
            elif platform != 'win32':
                filepath = cls.fix_path(filepath)
                if os.path.exists(filepath):
                    return filepath

            return ''

        path = DazPath.unquote(ref)
        filepath = path

        if path[2] == ":":
            filepath = path[1:]
            if Settings.verbosity > 2:
                print("Load", filepath)
        elif path[0] == "/":
            for folder in cls.paths:
                filepath = folder + path
                filepath = filepath.replace("//", "/")
                okpath = getExistingPath(filepath)
                if okpath:
                    return okpath

                words = filepath.rsplit("/", 2)

                if len(words) == 3 and words[1].lower() == "hiddentemp":
                    okpath = getExistingPath("%s/%s" % (words[0], words[2]))
                    if okpath:
                        return okpath

        if os.path.exists(filepath):
            if Settings.verbosity > 2:
                print("Found", filepath)
            return filepath

        if path.startswith("name:/@selection"):
            return ''

        if strict:
            Settings.missingAssets_[ref] = True
            msg = f"Did not find path:\n\"{path}\"\nRef:\"{ref}\""
            # raise ValueError()
            # print(msg)

            # ErrorsStatic.report(msg, trigger=(3, 4))

        return ''

    @classmethod
    def clear(cls):
        cls.paths = []

    @classmethod
    def clear_import(cls):
        cls.import_paths = []

    