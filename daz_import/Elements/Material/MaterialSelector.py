import bpy
from bpy.props import StringProperty, BoolProperty, CollectionProperty

from daz_import.Lib import Registrar
from .MaterialStatic import MaterialStatic
from daz_import.Elements.Color import ColorStatic


@Registrar()
class DazMaterialGroup(bpy.types.PropertyGroup):
    name: StringProperty()
    bool: BoolProperty()


class MaterialSelector:
    umats: CollectionProperty(type=DazMaterialGroup)

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.active_material)

    def draw(self, context):
        row = self.layout.row()
        row.operator("daz.select_all_materials")
        row.operator("daz.select_no_material")
        row = self.layout.row()
        row.operator("daz.select_skin_materials")
        row.operator("daz.select_skin_red_materials")
        umats = self.umats
        while umats:
            row = self.layout.row()
            row.prop(umats[0], "bool", text=umats[0].name)
            if len(umats) > 1:
                row.prop(umats[1], "bool", text=umats[1].name)
                umats = umats[2:]
            else:
                umats = []

    def setupMaterials(self, ob):
        self.skinColor = ColorStatic.WHITE

        for mat in ob.data.materials:
            if MaterialStatic.getSkinMaterial(mat) == "Skin":
                self.skinColor = mat.diffuse_color[0:3]
                break

        self.umats.clear()

        for mat in ob.data.materials:
            item = self.umats.add()
            item.name = mat.name
            item.bool = self.isDefaultActive(mat)

        MaterialStatic.getSkinMaterial(self)

    def useMaterial(self, mat):
        if mat.name in self.umats.keys():
            item = self.umats[mat.name]
            return item.bool
        else:
            return False

    def selectAll(self, context):
        for item in self.umats.values():
            item.bool = True

    def selectNone(self, context):
        for item in self.umats.values():
            item.bool = False

    def selectSkin(self, context):
        ob = context.object
        for mat, item in zip(ob.data.materials, self.umats.values()):
            item.bool = (mat.diffuse_color[0:3] == self.skinColor)

    def selectSkinRed(self, context):
        ob = context.object
        for mat, item in zip(ob.data.materials, self.umats.values()):
            item.bool = self.isSkinRedMaterial(mat)

    def isSkinRedMaterial(self, mat):
        if mat.diffuse_color[0:3] == self.skinColor:
            return True

        return MaterialStatic.getSkinMaterial(mat) == "Red"
