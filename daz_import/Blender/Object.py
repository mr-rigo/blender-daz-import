from __future__ import annotations
import bpy
from typing import Set, Any, Iterable, List


from daz_import.Lib.VectorStatic import Vector, VectorStatic


class Object:
    def __init__(self, obj: bpy.types.Object):
        self.inner = obj

    def is_mesh(self) -> bool:
        return self.inner.type == 'MESH'

    def is_hide(self) -> bool:
        return self.inner.hide_get() or self.inner.hide_viewport

    def is_visible(self) -> bool:
        return not self.is_hide()

    def is_armature(self) -> bool:
        return self.inner.type == 'ARMATURE'

    def is_selected(self) -> bool:
        return self.inner.select_get()

    def select(self, value: bool = True) -> bool:
        try:
            self.inner.select_set(value)
            return True
        except:
            return False

    def rig_parent(self) -> Object:
        par = self.parent()
        while par and par.is_armature():
            par = par.parent()
        return par

    def parent(self) -> Object:
        if obj := self.inner.parent:
            return Object(obj)

    def mesh_children(self) -> Iterable[Object]:
        for obj in self.children():
            if obj.is_mesh():
                yield obj
            else:
                yield from obj.mesh_children()

    def has_transforms(self) -> bool:
        return self.inner.location != VectorStatic.zero \
            or Vector(self.inner.rotation_euler) != VectorStatic.zero\
            or self.inner.scale != VectorStatic.one

    def children(self) -> Iterable[Object]:
        for child in self.inner.children:
            yield Object(child)

    def activate(self, context: bpy.types.Object):
        try:
            context.view_layer.objects.active = self.inner
            return True
        except:
            return False

    def unlink(self):
        for coll in bpy.data.collections:
            coll.objects.unlink(self.inner)
