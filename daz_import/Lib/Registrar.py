import bpy
from importlib import import_module
from typing import List, Tuple, Type, Callable
from daz_import.Lib.Settings.Paths import Paths


class Registrar(object):
    _classes: List[Tuple[Tuple, Type]] = []
    _functions: List[Callable] = []
    _undo_functions: List[Callable] = []

    def __init__(self, version: Tuple = None):
        self.version = version if version else tuple()

    def __call__(self, cls):
        self._classes.append((self.version, cls))
        return cls

    @classmethod
    def register(cls):
        for version, cls_ in cls._classes:
            if not version or (bpy.app.version and bpy.app.version >= version):
                bpy.utils.register_class(cls_)

        for func in cls._functions:
            func()

    @classmethod
    def unregister(cls):
        for version, cls_ in cls._classes:
            if not version or bpy.app.version >= version:
                bpy.utils.unregister_class(cls_)

        for func in cls._undo_functions:
            func()

    @classmethod
    def func(cls, func: Callable):
        cls._functions.append(func)
        return func

    @classmethod
    def undo_func(cls, func: Callable):
        cls._undo_functions.append(func)
        return func

    @classmethod
    def import_modules(cls, path: str):
        folder = Paths.parent(path)
        package = folder
        package = Paths.get_name(package)

        for file in Paths.children(folder):
            if Paths.is_folder(file):
                if Paths.get_name(file) == '__pycache__':
                    continue
                if not Paths.exists(Paths.join(file, '__init__.py')):
                    continue
                file = Paths.get_name(file)
                import_module("." + file, package)

            file = Paths.get_name(file, True)
            if file.find("__") == 0 or\
                    not Paths.extension_equal(file, 'py'):
                continue

            file = Paths.get_name(file)
            import_module("." + file, package)
