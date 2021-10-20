import os
import importlib
import bpy
from collections import defaultdict
from daz_import.Lib import Registrar
from daz_import.Lib.Settings.Paths import Paths


bl_info = {
    "name": "DAZ (.duf, .dsf) importer",
    "author": "Thomas Larsson",
    "version": (1, 6, 0),
    "blender": (2, 91, 0),
    "location": "UI > Daz Importer",
    "description": "Import native DAZ files (.duf, .dsf)",
    "warning": "",
    "wiki_url": "http://diffeomorphic.blogspot.se/p/daz-importer-version-16.html",
    "tracker_url": "https://bitbucket.org/Diffeomorphic/daz_import/issues?status=new&status=open",
    "category": "Import-Export"}


Registrar.import_modules(__file__)


def register():
    Registrar.register()


def unregister():
    Registrar.unregister()


class Empty:
    def __init__(self, *_):
        self.__dict__ = defaultdict()
        self.__dict__.default_factory = Empty

    def __getattr__(self, key):
        obj = type(self)()
        self.__dict__[key] = obj
        return obj

    def __call__(self, *_, **__):
        ...


if not bpy.app.version:
    bpy.types = Empty()


if __name__ == "__main__":
    # Registrar.register()
    print(bpy.types.data)
