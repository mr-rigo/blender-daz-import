import bpy
from daz_import.Lib import Registrar
from daz_import.utils import *
from .ImportDAZ import ImportOperator, import_daz_file
from .Operators import *
from .tools import *
from .EasyImportDAZ import EasyImportDAZ


def menu_func_import(self, _):
    self.layout.operator(ImportOperator.bl_idname, text="DAZ (.duf, .dsf)")
    self.layout.operator(EasyImportDAZ.bl_idname, text="Easy DAZ (.duf, .dsf)")


@Registrar.func
def register():
    bpy.types.Scene.DazFavoPath = StringProperty(
        name="Favorite Morphs",
        description="Path to favorite morphs",
        subtype='FILE_PATH',
        default="")
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


@Registrar.undo_func
def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
