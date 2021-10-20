from mathutils import Vector
from typing import Set, Iterable, List
import bpy

from .Errors import DazError
from .VectorStatic import VectorStatic
from .BlenderObjectStatic import BlenderObjectStatic


class BlenderStatic:

    @classmethod
    def visible_objects(cls, context: bpy.types.Context) -> Set[bpy.types.Object]:
        out = set()
        for ob in context.view_layer.objects:
            if BlenderObjectStatic.is_visible(ob):
                out.add(ob)
        return out

        # return [ob for ob in context.view_layer.objects
        #         if not (ob.hide_get() or ob.hide_viewport)]

    @classmethod
    def visible_meshes(cls, context: bpy.types.Context) -> Set[bpy.types.Mesh]:
        out = set()
        for ob in context.view_layer.objects:
            if BlenderObjectStatic.is_mesh(ob)\
                    and BlenderObjectStatic.is_visible(ob):
                out.add(ob)
        return out

        # return [ob for ob in context.view_layer.objects
        #         if ob.type == 'MESH' and not (ob.hide_get() or ob.hide_viewport)]

    @classmethod
    def selected(cls, context: bpy.types.Context) -> Set[bpy.types.Object]:
        out = set()
        for ob in context.view_layer.objects:
            if BlenderObjectStatic.is_selected(ob)\
                    and BlenderObjectStatic.is_visible(ob):
                out.add(ob)
        return out

        # return [ob for ob in context.view_layer.objects
        #         if ob.select_get() and not (ob.hide_get() or ob.hide_viewport)]

    @classmethod
    def selected_meshes(cls, context) -> Set[bpy.types.Mesh]:
        out = set()
        for ob in context.view_layer.objects:
            if BlenderObjectStatic.is_selected(ob)\
                    and BlenderObjectStatic.is_mesh(ob)\
                    and BlenderObjectStatic.is_visible(ob):
                out.add(ob)
        return out

        # return [ob for ob in context.view_layer.objects
        #         if ob.select_get() and ob.type == 'MESH' and not (ob.hide_get() or ob.hide_viewport)]

    @staticmethod
    def selected_armature(context) -> Set[bpy.types.Armature]:
        out = set()
        for ob in context.view_layer.objects:
            if BlenderObjectStatic.is_armature(ob)\
                    and BlenderObjectStatic.is_selected(ob) \
                    and BlenderObjectStatic.is_visible(ob):
                out.add(ob)
        return out

        # return [ob for ob in context.view_layer.objects
        #         if ob.select_get() and ob.type == 'ARMATURE' and not (ob.hide_get() or ob.hide_viewport)]

    @classmethod
    def active_object(cls, context, ob: bpy.types.Object = None) -> bpy.types.Object:
        if not ob:
            return context.view_layer.objects.active
        return cls.set_active_object(context, ob)

    @staticmethod
    def set_active_object(context, ob: bpy.types.Object) -> bool:
        try:
            context.view_layer.objects.active = ob
            return True
        except:
            return False

    @classmethod
    def in_collection(cls, layer, ob: bpy.types.Object) -> bool:
        if layer.hide_viewport:
            return False
        elif not layer.exclude and ob in layer.collection.objects.values():
            return True

        for child in layer.children:
            if cls.in_collection(child, ob):
                return True

        return False

    @staticmethod
    def collection(ob: bpy.types.Object) -> bpy.types.Collection:
        for coll in bpy.data.collections:
            if ob.name in coll.objects.keys():
                return coll
        return bpy.context.scene.collection

    @classmethod
    def activate(cls, context: bpy.types.Context, ob: bpy.types.Object) -> bool:
        try:
            context.view_layer.objects.active = ob

            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            BlenderObjectStatic.select(ob)
            cls.select(context, ob)
            return True
        except:
            print("Could not activate", ob.name)
            return False

    @staticmethod
    def set_mode(mode: str) -> None:
        try:
            bpy.ops.object.mode_set(mode=mode)
        except RuntimeError as err:
            raise DazError(err)

    @classmethod
    def select_list(cls, context: bpy.types.Context, objects: Iterable[bpy.types.Object]):
        cls.select(context, *objects)

    @classmethod
    def select(cls, context: bpy.types.Context, *objects: Iterable[bpy.types.Object]):
        if context.object:
            try:
                cls.set_mode('OBJECT')
            except:
                pass

        bpy.ops.object.select_all(action='DESELECT')

        for ob in objects:
            BlenderObjectStatic.select(ob)

    @staticmethod
    def unlink(*objects: bpy.types.Object):
        for ob in objects:
            for coll in bpy.data.collections:
                if ob in coll.objects.values():
                    coll.objects.unlink(ob)

    @classmethod
    def delete_list(cls, context: bpy.types.Context, objects: List[bpy.types.Object]):
        cls.delete(context, *objects)

    @classmethod
    def delete(cls, context: bpy.types.Context, *objects: bpy.types.Object):
        cls.select(context, *objects)
        bpy.ops.object.delete(use_global=False)

        for ob in objects:
            cls.unlink(ob)
            if ob:
                del ob

    @staticmethod
    def world_matrix(ob: bpy.types.Object, matrix) -> bool:
        if ob.parent:
            if ob.parent_type == 'OBJECT':
                ob.matrix_parent_inverse = ob.parent.matrix_world.inverted()
            elif ob.parent_type == 'BONE':
                pb = ob.parent.pose.bones[ob.parent_bone]
                ob.matrix_parent_inverse = pb.matrix.inverted()

        ob.matrix_world = matrix

        if Vector(ob.location).length < 1e-6:
            ob.location = VectorStatic.zero

        if Vector(ob.rotation_euler).length < 1e-6:
            ob.rotation_euler = VectorStatic.zero

        if (Vector(ob.scale) - VectorStatic.one).length < 1e-6:
            ob.scale = VectorStatic.one
        return False

    @staticmethod
    def is_location_unlocked(pb) -> bool:
        if pb.bone.use_connect:
            return False

        return pb.lock_location[0] == False \
            or pb.lock_location[1] == False \
            or pb.lock_location[2] == False

    @staticmethod
    def modifier(ob: bpy.types.Object, type_: str) -> bpy.types.Modifier:
        for mod in ob.modifiers:
            if mod.type == type_:
                return mod
        return None

    @staticmethod
    def constraint(ob: bpy.types.Object, type_: str) -> bpy.types.Constraint:
        for cns in ob.constraints:
            if cns.type == type_:
                return cns
        return None

    @staticmethod
    def clear_scene():
        for obj in bpy.context.scene.objects:
            obj.select_set(True)
        bpy.ops.object.delete()

    @classmethod
    def createHiddenCollection(cls, context, ob):
        parcoll = cls.collection(ob)
        for coll in parcoll.children:
            if coll.name.startswith("Hidden"):
                return coll
        coll = bpy.data.collections.new(name="Hidden")
        parcoll.children.link(coll)

        layer = cls.find_layer_collection(
            context.view_layer.layer_collection, coll)
        if layer:
            layer.exclude = True

        return coll

    @classmethod
    def find_layer_collection(cls, layer, coll):
        if layer.collection == coll:
            return layer
        for child in layer.children:
            clayer = cls.find_layer_collection(child, coll)
            if clayer:
                return clayer
        return None
