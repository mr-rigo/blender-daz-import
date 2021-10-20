from typing import Set, Any, Iterable, List
import bpy
from daz_import.Lib.VectorStatic import Vector, VectorStatic


class BlenderObjectStatic:

    @staticmethod
    def is_mesh(ob: bpy.types.Object) -> bool:
        return ob.type == 'MESH'

    @staticmethod
    def is_hide(ob: bpy.types.Object) -> bool:
        return ob.hide_get() or ob.hide_viewport

    @classmethod
    def is_visible(cls, ob: bpy.types.Object) -> bool:
        return not cls.is_hide(ob)

    @staticmethod
    def is_armature(ob: bpy.types.Object) -> bool:
        return ob.type == 'ARMATURE'

    @staticmethod
    def is_selected(ob: bpy.types.Object) -> bool:
        return ob.select_get()

    @staticmethod
    def select(ob: bpy.types.Object, value: bool = True) -> bool:
        try:
            ob.select_set(value)
            return True
        except:
            return False

    @classmethod
    def rig_parent(cls, ob: bpy.types.Object) -> bpy.types.Armature:
        par = ob.parent
        while par and cls.is_armature(par):
            par = par.parent
        return par

    @classmethod
    def mesh_children(cls, rig: bpy.types.Object) -> List[bpy.types.Mesh]:
        meshes = []
        for ob in rig.children:
            if ob.type == 'MESH':
                meshes.append(ob)
            else:
                meshes += cls.mesh_children(ob)
        return meshes

    @staticmethod
    def has_transforms(ob: bpy.types.Object) -> bool:
        return ob.location != VectorStatic.zero \
            or Vector(ob.rotation_euler) != VectorStatic.zero\
            or ob.scale != VectorStatic.one
