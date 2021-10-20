from daz_import.Lib import Registrar
from daz_import.Lib.Errors import DazOperator
from daz_import.Elements.Render import RenderStatic


@Registrar()
class DAZ_OT_UpdateSettings(DazOperator):
    bl_idname = "daz.update_settings"
    bl_label = "Update Render Settings"
    bl_description = "Update render and light settings if they are inadequate"
    bl_options = {'UNDO'}

    def run(self, context):
        RenderStatic.check(context, True)
