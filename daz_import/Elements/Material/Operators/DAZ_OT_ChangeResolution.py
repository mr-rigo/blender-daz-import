import os
import bpy
from daz_import.Lib import Registrar
from daz_import.Lib.Errors import DazOperator
from bpy.props import BoolProperty
from daz_import.Lib import BlenderStatic
from .ChangeResolution import ChangeResolution


@Registrar()
class DAZ_OT_ChangeResolution(DazOperator, ChangeResolution):
    bl_idname = "daz.change_resolution"
    bl_label = "Change Resolution"

    bl_description = (
        "Change all textures of selected meshes with resized versions.\n" +
        "The resized textures must already exist.")

    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.DazLocalTextures

    def draw(self, context):
        self.layout.prop(self, "steps")

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def run(self, context):
        self.overwrite = False
        paths = self.getAllTextures(context)
        self.getFileNames(paths.keys())
        self.replaceTextures(context)
