import bpy
from .DAZ_OT_SaveLocalTextures import DAZ_OT_SaveLocalTextures
from .DAZ_OT_MergeMaterials import DAZ_OT_MergeMaterials
from .DAZ_OT_CopyMaterials import DAZ_OT_CopyMaterials
from .MaterialMerger import MaterialMerger
from .ChangeResolution import ChangeResolution
from .DAZ_OT_ChangeResolution import DAZ_OT_ChangeResolution
from .DAZ_OT_ResizeTextures import DAZ_OT_ResizeTextures
from .DAZ_OT_UpdateSettings import DAZ_OT_UpdateSettings
from .DAZ_OT_PruneNodeTrees import DAZ_OT_PruneNodeTrees


from daz_import.Lib import Registrar
from bpy.props import EnumProperty, BoolProperty


@Registrar.func
def register():
    bpy.types.Object.DazLocalTextures = BoolProperty(default=False)

    bpy.types.Scene.DazHandleRenderSettings = EnumProperty(
        items=[("IGNORE", "Ignore", "Ignore insufficient render settings"),
               ("WARN", "Warn", "Warn about insufficient render settings"),
               ("UPDATE", "Update", "Update insufficient render settings")],
        name="Render Settings",
        default="UPDATE"
    )

    bpy.types.Scene.DazHandleLightSettings = EnumProperty(
        items=[("IGNORE", "Ignore", "Ignore insufficient light settings"),
               ("WARN", "Warn", "Warn about insufficient light settings"),
               ("UPDATE", "Update", "Update insufficient light settings")],
        name="Light Settings",
        default="UPDATE"
    )
