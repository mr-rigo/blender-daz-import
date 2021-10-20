import os
import bpy
from daz_import.Lib.Files import MultiFile, ImageFile
from daz_import.Lib import Registrar
from daz_import.Lib.Errors import DazOperator
from daz_import.Lib.Settings import Settings
from bpy.props import BoolProperty
from .ChangeResolution import ChangeResolution


@Registrar()
class DAZ_OT_ResizeTextures(DazOperator, ImageFile, MultiFile, ChangeResolution):
    bl_idname = "daz.resize_textures"
    bl_label = "Resize Textures"
    bl_description = (
        "Replace all textures of selected meshes with resized versions.\n" +
        "Python and OpenCV must be installed on your system.")
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.DazLocalTextures

    def draw(self, context):
        self.layout.prop(self, "steps")
        self.layout.prop(self, "resizeAll")

    def invoke(self, context, event):
        texpath = os.path.join(os.path.dirname(bpy.data.filepath), "textures/")
        self.properties.filepath = texpath
        return MultiFile.invoke(self, context, event)

    def run(self, context):
        if self.resizeAll:
            paths = self.getAllTextures(context)
        else:
            paths = self.getMultiFiles(Settings.theImageExtensions_)
        self.getFileNames(paths)

        program = os.path.join(os.path.dirname(
            __file__), "standalone/resize.py")
        folder = os.path.dirname(bpy.data.filepath)
        for path in paths:
            if path[0:2] == "//":
                path = os.path.join(folder, path[2:])
            _, newpath = self.getNewPath(self.getBasePath(path))
            if not os.path.exists(newpath):
                cmd = ('python "%s" "%s" "%s" %d' %
                       (program, path, newpath, self.steps))
                os.system(cmd)
            else:
                print("Skip", os.path.basename(newpath))

        self.replaceTextures(context)
