from daz_import.Lib.Errors import DazPropsOperator, IsMesh
from daz_import.Elements.Material import MaterialStatic
from daz_import.Lib import Registrar, BlenderStatic
from bpy.props import FloatVectorProperty


class ColorProp:
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.1, 0.1, 0.5, 1)
    )

    def draw(self, context):
        self.layout.prop(self, "color")


@Registrar()
class DAZ_OT_ChangeColors(DazPropsOperator, ColorProp):
    bl_idname = "daz.change_colors"
    bl_label = "Change Colors"
    bl_description = "Change viewport colors of all materials of this object"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            for mat in ob.data.materials:
                MaterialStatic.setDiffuse(mat, self.color)


@Registrar()
class DAZ_OT_ChangeSkinColor(DazPropsOperator, ColorProp, IsMesh):
    bl_idname = "daz.change_skin_color"
    bl_label = "Change Skin Colors"
    bl_description = "Change viewport colors of all materials of this object"
    bl_options = {'UNDO'}

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            for mat in ob.data.materials:
                MaterialStatic.guessMaterialColor(
                    mat, 'GUESS', True, self.color)
