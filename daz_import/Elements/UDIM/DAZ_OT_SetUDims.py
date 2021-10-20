from daz_import.Lib.Errors import DazPropsOperator
from bpy.props import IntProperty
from daz_import.Elements.Material import MaterialSelector
from daz_import.Lib import Registrar
from .UDimStatic import UDimStatic


@Registrar((2, 82, 0))
class DAZ_OT_SetUDims(DazPropsOperator, MaterialSelector):
    bl_idname = "daz.set_udims"
    bl_label = "Set UDIM Tile"
    bl_description = "Move all UV coordinates of selected materials to specified UV tile"
    bl_options = {'UNDO'}

    tile: IntProperty(name="Tile", min=1001, max=1100, default=1001)

    def draw(self, context):
        self.layout.prop(self, "tile")
        MaterialSelector.draw(self, context)

    def invoke(self, context, event):
        self.setupMaterials(context.object)
        return DazPropsOperator.invoke(self, context, event)

    def isDefaultActive(self, _):
        return False

    def run(self, context):

        ob = context.object
        vdim = (self.tile - 1001)//10
        udim = self.tile - 10*vdim
        tile = self.tile - 1001
        for mn, umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                UDimStatic.shiftUVs(mat, mn, ob, tile)
                UDimStatic.add(mat, udim - mat.DazUDim, vdim - mat.DazVDim)
                mat.DazUDim = udim
                mat.DazVDim = vdim
