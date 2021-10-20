
import bpy
from bpy.props import BoolProperty
from collections import OrderedDict

from daz_import.Lib import Registrar
from daz_import.Lib.BlenderStatic import BlenderStatic
from daz_import.Lib.Settings import Settings
from daz_import.Lib.Errors import DazOperator, IsArmature,\
    IsObject, DazError
from daz_import.Lib.Utility import Props, PropsStatic,\
    UtilityBoneStatic, UtilityStatic, Updating
from daz_import.Elements.Driver import *


# -------------------------------------------------------------
#   Check if RNA is driven
# -------------------------------------------------------------


def getDriver(rna, channel, idx):
    if rna.animation_data:
        for fcu in rna.animation_data.drivers:
            if fcu.data_path == channel and fcu.array_index == idx:
                return fcu
    return None


def isBoneDriven(rig, pb):
    return (getBoneDrivers(rig, pb) != [])


def getBoneDrivers(rig, pb):
    if rig.animation_data:
        path = 'pose.bones["%s"]' % pb.name
        return [fcu for fcu in rig.animation_data.drivers
                if (fcu.data_path.startswith(path) and
                    not fcu.data_path.endswith("HdOffset"))]
    else:
        return []


def getPropDrivers(rig):
    if rig.animation_data:
        return [fcu for fcu in rig.animation_data.drivers
                if fcu.data_path[0] == '[']
    else:
        return []


def getDrivingBone(fcu, rig):
    for var in fcu.driver.variables:
        if var.type == 'TRANSFORMS':
            trg = var.targets[0]
            if trg.id == rig:
                return trg.bone_target
    return None


def isFaceBoneDriven(rig, pb):
    if isBoneDriven(rig, pb):
        return True
    else:
        par = pb.parent
        return (par and UtilityBoneStatic.is_drv_bone(par.name) and isBoneDriven(rig, par))


def getShapekeyPropDriver(skeys, sname):
    return getRnaDriver(skeys, 'key_blocks["%s"].value' % (sname), 'SINGLE_PROP')


# -------------------------------------------------------------
#
# -------------------------------------------------------------


def addTransformVar(fcu, vname, ttype, rig, bname):
    pb = rig.pose.bones[bname]
    var = fcu.driver.variables.new()
    var.type = 'TRANSFORMS'
    var.name = vname
    trg = var.targets[0]
    trg.id = rig
    trg.bone_target = bname
    trg.rotation_mode = pb.rotation_mode
    trg.transform_type = ttype
    trg.transform_space = 'LOCAL_SPACE'

# -------------------------------------------------------------
#   Prop drivers
# -------------------------------------------------------------


def makePropDriver(path, rna, channel, rig, expr):
    rna.driver_remove(channel)
    fcu = rna.driver_add(channel)
    fcu.driver.type = 'SCRIPTED'
    fcu.driver.expression = expr
    removeModifiers(fcu)
    addDriverVar(fcu, "x", path, rig)


# -------------------------------------------------------------
#   Overridable properties
# -------------------------------------------------------------


def setPropMinMax(rna, prop, min, max):
    rna_ui = rna.get('_RNA_UI')
    if rna_ui is None:
        rna_ui = rna['_RNA_UI'] = {}
    struct = {"min": min,
              "max": max,
              "soft_min": min,
              "soft_max": max}
    rna_ui[prop] = struct


def getPropMinMax(rna, prop):
    rna_ui = rna.get('_RNA_UI')
    min = Settings.customMin
    max = Settings.customMax

    if rna_ui and prop in rna_ui.keys():
        struct = rna_ui[prop]

        if "min" in struct.keys():
            min = struct["min"]

        if "max" in struct.keys():
            max = struct["max"]

    return min, max


def truncateProp(prop):
    if len(prop) > 63:
        print('Truncate property "%s"' % prop)
        return prop[:63]
    else:
        return prop


def setFloatProp(rna, prop, value, min=None, max=None):
    value = float(value)
    prop = truncateProp(prop)
    rna[prop] = value
    if min is not None:
        min = float(min)
        max = float(max)
        setPropMinMax(rna, prop, min, max)
        Props.set_overridable(rna, prop)
        setPropMinMax(rna, prop, min, max)
    else:
        Props.set_overridable(rna, prop)


def setBoolProp(rna, prop, value, desc=""):
    prop = truncateProp(prop)
    #setattr(bpy.types.Object, prop, BoolProperty(default=value, description=desc))
    #setattr(rna, prop, value)
    rna[prop] = value
    setPropMinMax(rna, prop, 0, 1)
    Props.set_overridable(rna, prop)
    setPropMinMax(rna, prop, 0, 1)

# -------------------------------------------------------------
#
# -------------------------------------------------------------


def addDriverVar(fcu, vname, path, rna):
    var = fcu.driver.variables.new()
    var.name = vname
    var.type = 'SINGLE_PROP'
    trg = var.targets[0]
    trg.id_type = getIdType(rna)
    trg.id = rna
    trg.data_path = path
    return trg


def getIdType(rna) -> str:
    if isinstance(rna, bpy.types.Armature):
        return 'ARMATURE'
    elif isinstance(rna, bpy.types.Object):
        return 'OBJECT'
    elif isinstance(rna, bpy.types.Mesh):
        return 'MESH'
    else:
        raise RuntimeError("BUG addDriverVar", rna)


def hasDriverVar(fcu, dname, rig):
    path = PropsStatic.ref(dname)
    for var in fcu.driver.variables:
        trg = var.targets[0]
        if trg.id == rig and trg.data_path == path:
            return True
    return False


def getDriverPaths(fcu, rig):
    paths = {}
    for var in fcu.driver.variables:
        trg = var.targets[0]
        if trg.id == rig:
            paths[var.name] = trg.data_path
    return paths


def isNumber(string):
    try:
        float(string)
        return True
    except ValueError:
        return False


def removeDriverFCurves(fcus, rig):
    def flatten(lists):
        flat = []
        for list in lists:
            flat.extend(list)
        return flat

    for fcu in flatten(fcus):
        try:
            rig.driver_remove(fcu.data_path, fcu.array_index)
        except TypeError:
            pass


def isPropDriver(fcu):
    vars = fcu.driver.variables
    return (len(vars) > 0 and vars[0].type == 'SINGLE_PROP')


# ----------------------------------------------------------
#   Bone sum drivers
# ----------------------------------------------------------

def getAllBoneSumDrivers(rig, bnames):    
    boneFcus = OrderedDict()
    sumFcus = OrderedDict()

    if rig.animation_data is None:
        return boneFcus, sumFcus

    for fcu in rig.animation_data.drivers:
        words = fcu.data_path.split('"', 2)

        if words[0] == "pose.bones[":
            bname = UtilityBoneStatic.base(words[1])
            if bname not in bnames:
                continue
        else:
            if words[0] != "[":
                print("MISS", words)
            continue
        
        if fcu.driver.type == 'SCRIPTED':
            if bname not in boneFcus.keys():
                boneFcus[bname] = []
            boneFcus[bname].append(fcu)
        elif fcu.driver.type == 'SUM':
            if bname not in sumFcus.keys():
                sumFcus[bname] = []
            sumFcus[bname].append(fcu)
    return boneFcus, sumFcus


def removeBoneSumDrivers(rig, bones):
    boneFcus, sumFcus = getAllBoneSumDrivers(rig, bones)
    removeDriverFCurves(boneFcus.values(), rig)
    removeDriverFCurves(sumFcus.values(), rig)

# ----------------------------------------------------------
#   Update button
# ----------------------------------------------------------


# def updateDrivers2(rna):
#     if rna and rna.animation_data:
#         for fcu in rna.animation_data.drivers:
#             if fcu.driver.type == 'SCRIPTED':
#                 fcu.driver.expression = str(fcu.driver.expression)


@Registrar()
class DAZ_OT_UpdateAll(DazOperator):
    bl_idname = "daz.update_all"
    bl_label = "Update All"
    bl_description = "Update everything. Try this if driven bones are messed up"
    bl_options = {'UNDO'}

    def run(self, context):
        Updating.scene(context)
        for ob in context.scene.collection.all_objects:
            Updating.drivers(ob)

# ----------------------------------------------------------
#   Retarget mesh drivers
# ----------------------------------------------------------


@Registrar()
class DAZ_OT_RetargetDrivers(DazOperator, IsArmature):
    bl_idname = "daz.retarget_mesh_drivers"
    bl_label = "Retarget Mesh Drivers"
    bl_description = "Retarget drivers of selected objects to active object"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for ob in BlenderStatic.selected(context):
            if ob != rig:
                self.retargetRna(ob, rig)
                if ob.data:
                    self.retargetRna(ob.data, rig)
                if ob.type == 'MESH' and ob.data.shape_keys:
                    self.retargetRna(ob.data.shape_keys, rig)

    def retargetRna(self, rna, rig):
        from daz_import.Elements.Morph import addToCategories
        if rna and rna.animation_data:
            props = {}
            for fcu in rna.animation_data.drivers:
                for var in fcu.driver.variables:
                    if var.type == 'SINGLE_PROP':
                        trg = var.targets[0]
                        words = trg.data_path.split('"')
                        if len(words) == 3:
                            prop = words[1]
                            if prop not in rig.keys():
                                min, max, cat = self.getOldData(trg, prop)
                                if cat not in props.keys():
                                    props[cat] = []
                                props[cat].append(prop)
                                setFloatProp(rig, prop, 0.0, min, max)
                    for trg in var.targets:
                        if trg.id_type == getIdType(rig):
                            trg.id = rig
            if props:
                for cat, cprops in props.items():
                    addToCategories(rig, cprops, cat)
                rig.DazCustomMorphs = True
            Updating.drivers(rig)

    def getOldData(self, trg, prop):
        from daz_import.Elements.Morph import getMorphCategory

        if not trg.id:
            return Settings.customMin, Settings.customMax, "Shapes"

        min = Settings.customMin
        max = Settings.customMax
        rna_ui = trg.id.get('_RNA_UI')
        if rna_ui and "min" in rna_ui.keys():
            min = rna_ui["min"]
        if rna_ui and "max" in rna_ui.keys():
            max = rna_ui["max"]
        cat = getMorphCategory(trg.id, prop)
        return min, max, cat

# ----------------------------------------------------------
#   Copy props
# ----------------------------------------------------------


@Registrar()
class DAZ_OT_CopyProps(DazOperator):
    pool = IsObject.pool
    bl_idname = "daz.copy_props"
    bl_label = "Copy Props"
    bl_description = "Copy properties from selected objects to active object"
    bl_options = {'UNDO'}

    @staticmethod
    def run(context):
        rig = context.object
        for ob in BlenderStatic.selected(context):
            if ob == rig:
                continue
            for key in ob.keys():
                if key not in rig.keys():
                    rig[key] = ob[key]


# ----------------------------------------------------------
#   Copy drivers
# ----------------------------------------------------------


@Registrar()
class DAZ_OT_CopyBoneDrivers(DazOperator, DriverUser):
    pool = IsArmature.pool
    bl_idname = "daz.copy_bone_drivers"
    bl_label = "Copy Bone Drivers"
    bl_description = "Copy bone drivers from selected rig to active rig"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        for ob in BlenderStatic.selected_armature(context):
            if ob != rig:
                self.createTmp()
                try:
                    self.copyBoneDrivers(ob, rig)
                finally:
                    self.deleteTmp()
                return
        raise DazError("Need two selected armatures")

    def copyBoneDrivers(self, rig1, rig2):
        if rig1.animation_data:
            struct = {}
            for fcu in rig1.animation_data.drivers:
                words = fcu.data_path.split('"')
                if (len(words) == 3 and
                        words[0] == "pose.bones["):
                    bname = words[1]
                    if bname not in rig2.data.bones.keys():
                        print("Missing bone (copyBoneDrivers):", bname)
                        continue
                    fcu2 = self.copyDriver(fcu, rig2)
                    self.setId(fcu2, rig1, rig2)

# ----------------------------------------------------------
#   Disable and enable drivers
# ----------------------------------------------------------


def muteDazFcurves(rig, mute):
    def isDazFcurve(path):
        for string in ["(fin)", "(rst)", ":Loc:", ":Rot:", ":Sca:"]:
            if string in path:
                return True
        return False

    if rig and rig.data.animation_data:
        for fcu in rig.data.animation_data.drivers:
            if isDazFcurve(fcu.data_path):
                fcu.mute = mute
    for ob in rig.children:
        if ob.type != 'MESH':
            continue

        skeys = ob.data.shape_keys
        if not(skeys and skeys.animation_data):
            continue

        for fcu in skeys.animation_data.drivers:
            words = fcu.data_path.split('"')
            if words[0] != "key_blocks[":
                continue

            fcu.mute = mute
            sname = words[1]
            if sname not in skeys.key_blocks.keys():
                continue

            skey = skeys.key_blocks[sname]
            skey.mute = mute


@Registrar()
class DAZ_OT_DisableDrivers(DazOperator):
    bl_idname = "daz.disable_drivers"
    bl_label = "Disable Drivers"
    bl_description = "Disable all drivers to improve performance"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazDriversDisabled)

    def run(self, context):
        BlenderStatic.set_mode('OBJECT')
        for rig in BlenderStatic.selected_armature(context):
            muteDazFcurves(rig, True)
            rig.DazDriversDisabled = True


@Registrar()
class DAZ_OT_EnableDrivers(DazOperator):
    bl_idname = "daz.enable_drivers"
    bl_label = "Enable Drivers"
    bl_description = "Enable all drivers"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazDriversDisabled)

    def run(self, context):
        BlenderStatic.set_mode('OBJECT')

        for rig in BlenderStatic.selected_armature(context):
            muteDazFcurves(rig, False)
            rig.DazDriversDisabled = False

# ----------------------------------------------------------
#   Initialize
# ----------------------------------------------------------


@Registrar.func
def register():
    bpy.types.Object.DazDriversDisabled = BoolProperty(default=False)
