
import bpy
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib import Registrar
#from daz_import.drivers import *
from daz_import.utils import *
from daz_import.Lib.Errors import *
from bpy.props import *


def getMaskName(string):
    return "Mask_" + string.split(".", 1)[0]


def getHidePropName(string):
    return "Mhh" + string.split(".", 1)[0]


def isHideProp(string):
    return (string[0:3] == "Mhh")


def getMannequinName(string):
    return "MhhMannequin"

# ------------------------------------------------------------------------
#   Object selection
# ------------------------------------------------------------------------


class MeshSelection:
    def draw(self, context):
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_none")
        for pg in context.scene.DazSelector:
            row = self.layout.row()
            row.prop(pg, "select", text="")
            row.label(text=pg.text)

    def selectAll(self, context):
        for pg in context.scene.DazSelector:
            pg.select = True

    def selectNone(self, context):
        for pg in context.scene.DazSelector:
            pg.select = False

    def getSelection(self, context):
        selected = []
        for pg in context.scene.DazSelector:
            if pg.select:
                ob = bpy.data.objects[pg.text]
                selected.append(ob)
        return selected

    def invoke(self, context, event):
        from daz_import.Elements.Morph import MorphSelector
                
        MorphSelector.set(self)
        scn = context.scene
        pgs = scn.DazSelector
        pgs.clear()
        for ob in BlenderStatic.visible_meshes(context):
            if ob != context.object:
                pg = pgs.add()
                pg.text = ob.name
                pg.select = False
        return DazPropsOperator.invoke(self, context, event)

# ------------------------------------------------------------------------
#    Setup: Add and remove hide drivers
# ------------------------------------------------------------------------


class SingleGroup:
    singleGroup: BoolProperty(
        name="Single Group",
        description="Treat all selected meshes as a single group",
        default=False)

    groupName: StringProperty(
        name="Group Name",
        description="Name of the single group",
        default="All")


@Registrar()
class DAZ_OT_AddVisibility(DazPropsOperator, MeshSelection, SingleGroup, IsArmature):
    bl_idname = "daz.add_visibility_drivers"
    bl_label = "Add Visibility Drivers"
    bl_description = "Control visibility with rig property. For file linking."
    bl_options = {'UNDO'}

    useCollections: BoolProperty(
        name="Add Collections",
        description="Move selected meshes to new collections",
        default=True)

    def draw(self, context):
        self.layout.prop(self, "singleGroup")
        if self.singleGroup:
            self.layout.prop(self, "groupName")
        self.layout.prop(self, "useCollections")
        MeshSelection.draw(self, context)

    def invoke(self, context, event):
        return MeshSelection.invoke(self, context, event)

    def run(self, context):
        rig = context.object
        print("Create visibility drivers for %s:" % rig.name)
        selected = self.getSelection(context)
        if self.singleGroup:
            obnames = [self.groupName]
            for ob in selected:
                self.createObjectVisibility(rig, ob, self.groupName)
        else:
            obnames = []
            for ob in selected:
                self.createObjectVisibility(rig, ob, ob.name)
                obnames.append(ob.name)
        for ob in rig.children:
            if ob.type == 'MESH':
                self.createMaskVisibility(rig, ob, obnames)
                ob.DazVisibilityDrivers = True
        rig.DazVisibilityDrivers = True
        Updating.drivers(rig)

        if self.useCollections:
            self.addCollections(context, rig, selected)

        print("Visibility drivers created")

    def createObjectVisibility(self, rig, ob, obname):
        from daz_import.driver import setBoolProp, makePropDriver
        prop = getHidePropName(obname)
        setBoolProp(rig, prop, True, "Show %s" % prop)
        makePropDriver(PropsStatic.ref(prop), ob, "hide_viewport", rig, expr="not(x)")
        makePropDriver(PropsStatic.ref(prop), ob, "hide_render", rig, expr="not(x)")

    def createMaskVisibility(self, rig, ob, obnames):
        from daz_import.driver import makePropDriver
        props = {}
        for obname in obnames:
            modname = getMaskName(obname)
            props[modname] = getHidePropName(obname)
        masked = False
        for mod in ob.modifiers:
            if (mod.type == 'MASK' and
                    mod.name in props.keys()):
                prop = props[mod.name]
                makePropDriver(PropsStatic.ref(prop), mod,
                               "show_viewport", rig, expr="x")
                makePropDriver(PropsStatic.ref(prop), mod,
                               "show_render", rig, expr="x")

    def addCollections(self, context, rig, selected):
        rigcoll = BlenderStatic.collection(rig)
        if rigcoll is None:
            raise DazError("No collection found")
        print("Create visibility collections for %s:" % rig.name)
        if self.singleGroup:
            coll = createSubCollection(rigcoll, self.groupName)
            for ob in selected:
                moveToCollection(ob, coll)
        else:
            for ob in selected:
                coll = createSubCollection(rigcoll, ob.name)
                moveToCollection(ob, coll)
        rig.DazVisibilityCollections = True
        print("Visibility collections created")

# ------------------------------------------------------------------------
#   Collections
# ------------------------------------------------------------------------


def createSubCollection(coll, cname):
    subcoll = bpy.data.collections.new(cname)
    coll.children.link(subcoll)
    return subcoll


def moveToCollection(ob, newcoll):
    if newcoll is None:
        return
    for coll in bpy.data.collections:
        if ob in coll.objects.values():
            coll.objects.unlink(ob)
        if ob not in newcoll.objects.values():
            newcoll.objects.link(ob)

# ------------------------------------------------------------------------
#   Remove visibility
# ------------------------------------------------------------------------


@Registrar()
class DAZ_OT_RemoveVisibility(DazOperator):
    bl_idname = "daz.remove_visibility_drivers"
    bl_label = "Remove Visibility Drivers"
    bl_description = "Remove ability to control visibility from rig property"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazVisibilityDrivers)

    def run(self, context):
        rig = context.object
        for ob in rig.children:
            ob.driver_remove("hide_viewport")
            ob.driver_remove("hide_render")
            ob.hide_set(False)
            ob.hide_viewport = False
            ob.hide_render = False
            for mod in ob.modifiers:
                if mod.type == 'MASK':
                    mod.driver_remove("show_viewport")
                    mod.driver_remove("show_render")
                    mod.show_viewport = True
                    mod.show_render = True
        for prop in rig.keys():
            if isHideProp(prop):
                del rig[prop]
        Updating.drivers(rig)
        rig.DazVisibilityDrivers = False
        print("Visibility drivers removed")

# ------------------------------------------------------------------------
#   Show/Hide all
# ------------------------------------------------------------------------


class SetAllVisibility:
    prefix: StringProperty()

    def run(self, context):
        from daz_import.Elements.Morph import autoKeyProp, getRigFromObject
        
        rig = getRigFromObject(context.object)
        scn = context.scene
        if rig is None:
            return
        for key in rig.keys():
            if key[0:3] == "Mhh":
                if key:
                    rig[key] = self.on
                    autoKeyProp(rig, key, scn, scn.frame_current, True)
        Updating.drivers(rig)


@Registrar()
class DAZ_OT_ShowAllVis(DazOperator, SetAllVisibility):
    bl_idname = "daz.show_all_vis"
    bl_label = "Show All"
    bl_description = "Show all meshes/makeup of this rig"

    on = True


@Registrar()
class DAZ_OT_HideAllVis(DazOperator, SetAllVisibility):
    bl_idname = "daz.hide_all_vis"
    bl_label = "Hide All"
    bl_description = "Hide all meshes/makeup of this rig"

    on = False


@Registrar()
class DAZ_OT_ToggleVis(DazOperator, IsMeshArmature):
    bl_idname = "daz.toggle_vis"
    bl_label = "Toggle Vis"
    bl_description = "Toggle visibility of this mesh"

    name: StringProperty()

    def run(self, context):
        from daz_import.Elements.Morph import getRigFromObject, autoKeyProp
        rig = getRigFromObject(context.object)
        scn = context.scene
        if rig:
            rig[self.name] = not rig[self.name]
            autoKeyProp(rig, self.name, scn, scn.frame_current, True)
            Updating.drivers(rig)

# ------------------------------------------------------------------------
#   Mask modifiers
# ------------------------------------------------------------------------


@Registrar()
class DAZ_OT_CreateMasks(DazPropsOperator, MeshSelection, SingleGroup):
    bl_idname = "daz.create_masks"
    bl_label = "Create Masks"
    bl_description = "Create vertex groups and mask modifiers in active mesh for selected meshes"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def draw(self, context):
        self.layout.prop(self, "singleGroup")
        if self.singleGroup:
            self.layout.prop(self, "groupName")
        else:
            MeshSelection.draw(self, context)

    def run(self, context):
        print("Create masks for %s:" % context.object.name)
        if self.singleGroup:
            modname = getMaskName(self.groupName)
            print("  ", modname)
            self.createMask(context.object, modname)
        else:
            for ob in self.getSelection(context):
                modname = getMaskName(ob.name)
                print("  ", ob.name, modname)
                self.createMask(context.object, modname)
        print("Masks created")

    def createMask(self, ob, modname):
        mod = None
        for mod1 in ob.modifiers:
            if mod1.type == 'MASK' and mod1.name == modname:
                mod = mod1
        if modname in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups[modname]
        else:
            vgrp = ob.vertex_groups.new(name=modname)
        if mod is None:
            mod = ob.modifiers.new(modname, 'MASK')
        mod.vertex_group = modname
        mod.invert_vertex_group = True

    def invoke(self, context, event):
        return MeshSelection.invoke(self, context, event)

# ------------------------------------------------------------------------
#   Shrinkwrap
# ------------------------------------------------------------------------


@Registrar()
class DAZ_OT_AddShrinkwrap(DazPropsOperator, MeshSelection, IsMesh):
    bl_idname = "daz.add_shrinkwrap"
    bl_label = "Add Shrinkwrap"
    bl_description = "Add shrinkwrap modifiers covering the active mesh.\nOptionally add solidify modifiers"
    bl_options = {'UNDO'}

    offset: FloatProperty(
        name="Offset (mm)",
        description="Offset the surface from the character mesh",
        default=2.0)

    useSolidify: BoolProperty(
        name="Solidify",
        description="Add a solidify modifier too",
        default=False)

    thickness: FloatProperty(
        name="Thickness (mm)",
        description="Thickness of the surface",
        default=2.0)

    useApply: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers afterwards",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "offset")
        self.layout.prop(self, "useSolidify")
        if self.useSolidify:
            self.layout.prop(self, "thickness")
        self.layout.prop(self, "useApply")
        MeshSelection.draw(self, context)

    def run(self, context):
        hum = context.object
        for ob in self.getSelection(context):
            BlenderStatic.activate(context, ob)
            self.makeShrinkwrap(ob, hum)
            if self.useSolidify:
                self.makeSolidify(ob)

    def makeShrinkwrap(self, ob, hum):
        mod = None
        for mod1 in ob.modifiers:
            if mod1.type == 'SHRINKWRAP' and mod1.target == hum:
                print("Object %s already has shrinkwrap modifier targeting %s" % (
                    ob.name, hum.name))
                mod = mod1
                break
        if mod is None:
            mod = ob.modifiers.new(hum.name, 'SHRINKWRAP')
        mod.target = hum
        mod.wrap_method = 'NEAREST_SURFACEPOINT'
        mod.wrap_mode = 'OUTSIDE'
        mod.offset = 0.1*hum.DazScale*self.offset
        if self.useApply and not ob.data.shape_keys:
            bpy.ops.object.modifier_apply(modifier=mod.name)

    def makeSolidify(self, ob):
        mod = BlenderStatic.modifier(ob, 'SOLIDIFY')
        if mod:
            print("Object %s already has solidify modifier" % ob.name)
        else:
            mod = ob.modifiers.new("Solidify", 'SOLIDIFY')
        mod.thickness = 0.1*ob.DazScale*self.thickness
        mod.offset = 0.0
        if self.useApply and not ob.data.shape_keys:
            bpy.ops.object.modifier_apply(modifier=mod.name)

    def invoke(self, context, event):
        return MeshSelection.invoke(self, context, event)

# ----------------------------------------------------------
#   Initialize
# ----------------------------------------------------------


@Registrar.func
def register():
    bpy.types.Object.DazVisibilityDrivers = BoolProperty(default=False)
    bpy.types.Object.DazVisibilityCollections = BoolProperty(default=False)
