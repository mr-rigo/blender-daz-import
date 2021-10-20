import bpy
import os

from daz_import.Lib.Settings import Settings
from daz_import.Lib import Registrar


@Registrar()
class ErrorOperator(bpy.types.Operator):
    bl_idname = "daz.error"
    bl_label = "Daz Importer"

    def execute(self, context):
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        Settings.theErrorLines_ = Settings.theMessage_.split('\n')

        maxlen = len(self.bl_label)
        for line in Settings.theErrorLines_:
            if len(line) > maxlen:
                maxlen = len(line)

        width = 20+5*maxlen
        height = 20+5*len(Settings.theErrorLines_)

        #self.report({'INFO'}, Settings.theMessage)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=width)

    def draw(self, context):
        for line in Settings.theErrorLines_:
            self.layout.label(text=line)
