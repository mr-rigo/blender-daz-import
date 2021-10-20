import bpy
import os
from typing import List
from daz_import.Collection.Collection import Collection


class FilePath:

    @staticmethod
    def getTypedFilePath(filepath: str, exts: List[str]) -> str:
        words = os.path.splitext(filepath)

        if len(words) == 2:
            fname, ext = words
        else:
            return None

        if fname[-4:] == ".tip":
            fname = fname[:-4]
        if ext in [".png", ".jpeg", ".jpg", ".bmp"]:
            if os.path.exists(fname):
                words = os.path.splitext(fname)
                if (len(words) == 2 and
                        words[1][1:] in exts):
                    return fname
            for ext1 in exts:
                path = fname+"."+ext1
                if os.path.exists(path):
                    return path
            return None
        elif ext[1:].lower() in exts:
            return filepath
        else:
            return None

    @staticmethod
    def getExistingFilePath(filepath: str, ext: str) -> str:
        filepath: str = bpy.path.ensure_ext(bpy.path.abspath(filepath), ext)
        filepath = os.path.expanduser(filepath).replace("\\", "/")

        if os.path.exists(filepath):
            return filepath
        else:
            raise FileExistsError('File does not exist:\n"%s"' % filepath)
            # raise DazError('File does not exist:\n"%s"' % filepath)

    @staticmethod
    def getFolders(ob, sub_dirs: List[str]) -> List[str]:
        if ob is None:
            return []

        fileref = ob.DazUrl.split("#")[0]
        if len(fileref) < 2:
            return []

        reldir = os.path.dirname(fileref)
        folders = []

        for basedir in Collection.get_paths():
            for subdir in sub_dirs:
                folder = "%s/%s/%s" % (basedir, reldir, subdir)
                folder = folder.replace("//", "/")
                if os.path.exists(folder):
                    folders.append(folder)

        return folders

    @staticmethod
    def safeOpen(filepath, rw: str, dirMustExist=False, fileMustExist=False, mustOpen=False):
        if dirMustExist:
            folder = os.path.dirname(filepath)
            if not os.path.exists(folder):
                raise FileNotFoundError(
                    f"Directory does not exist:      \n{folder}")
                # raise DazError(f"Directory does not exist:      \n{folder}")

        if fileMustExist:
            if not os.path.exists(filepath):
                raise FileNotFoundError(
                    f"""File does not exist:     \n{filepath}""")
                # raise DazError(f"""File does not exist:     \n{filepath}""")

        if rw == "w":
            encoding = "utf_8"
        else:
            encoding = "utf_8_sig"

        try:
            fp = open(filepath, rw, encoding=encoding)
        except FileNotFoundError:
            fp = None

        if fp is None:
            if rw[0] == "r":
                mode = "reading"
            else:
                mode = "writing"
            msg = ("Could not open file for %s:   \n" % mode +
                   "%s          " % filepath)
            if mustOpen:
                raise FileNotFoundError(msg)
                # raise DazError(msg)
            # ErrorsStatic.report(msg, warnPaths=True, trigger=(2, 4))
        return fp

    @staticmethod
    def getMultiFiles(files: List[str], extensions: List[str], folder: str) -> List[str]:
        filepaths = []

        if Collection.import_paths:
            for path in Collection.import_paths:
                filepath = FilePath.getTypedFilePath(path, extensions)
                if filepath:
                    filepaths.append(filepath)
        else:
            for file_elem in files:
                path = os.path.join(folder, file_elem.name)
                if os.path.isfile(path):
                    filepath = FilePath.getTypedFilePath(path, extensions)
                    if filepath:
                        filepaths.append(filepath)
        return filepaths
