from mathutils import Vector
from typing import Set, Iterable, List
import bpy

from daz_import.Lib.VectorStatic import VectorStatic
from .Object import Object


class Blender:

    @classmethod
    def visible_objects(cls, context: bpy.types.Context) -> Iterable[Object]:
        for ob in context.view_layer.objects:
            ob = Object(ob)
            if ob.is_visible():
                yield ob

    @classmethod
    def visible_meshes(cls, context: bpy.types.Context) -> Iterable[Object]:
        for ob in context.view_layer.objects:
            ob = Object(ob)
            if ob.is_mesh() and ob.is_visible():
                yield ob

    @classmethod
    def selected(cls, context: bpy.types.Context) -> Iterable[Object]:
        for ob in context.view_layer.objects:
            ob = Object(ob)
            if ob.is_selected() and ob.is_visible():
                yield ob

    @classmethod
    def selected_meshes(cls, context: bpy.types.Context) -> Iterable[Object]:
        for ob in context.view_layer.objects:
            ob = Object(ob)
            if ob.is_selected() and ob.is_visible() and ob.is_mesh():
                yield ob

    @staticmethod
    def selected_armature(context) -> Set[bpy.types.Armature]:
        for ob in context.view_layer.objects:
            ob = Object(ob)
            if ob.is_selected() and ob.is_visible() and ob.is_armature():
                yield ob

    @staticmethod
    def set_mode(mode: str) -> None:
        bpy.ops.object.mode_set(mode=mode)

    @classmethod
    def set_mode_edit(cls):
        cls.set_mode('EDIT')

    @classmethod
    def set_mode_object(cls):
        cls.set_mode('OBJECT')

    @classmethod
    def set_mode_pose(cls):
        cls.set_mode('POSE')
