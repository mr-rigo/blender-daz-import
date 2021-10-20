import bpy
import os
from mathutils import Vector
from bpy.props import BoolProperty, IntProperty

from daz_import.driver import DriverUser
from daz_import.Lib import Registrar
from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Lib.BlenderStatic import BlenderStatic
from daz_import.Lib.BlenderObjectStatic import BlenderObjectStatic

from daz_import.Lib.Errors import DazOperator, \
    DazPropsOperator, IsArmature

from daz_import.Lib.Utility import  PropsStatic, UtilityBoneStatic

# -------------------------------------------------------------
#   Fixer class
# -------------------------------------------------------------


class Fixer(DriverUser):

    def fixPelvis(self, rig):
        BlenderStatic.set_mode('EDIT')
        hip = rig.data.edit_bones["hip"]
        if hip.tail[2] > hip.head[2]:
            for child in hip.children:
                child.use_connect = False
            head = Vector(hip.head)
            tail = Vector(hip.tail)
            hip.head = Vector((1, 2, 3))
            hip.tail = head
            hip.head = tail
        if "pelvis" not in rig.data.bones.keys():
            pelvis = rig.data.edit_bones.new("pelvis")
            pelvis.head = hip.head
            pelvis.tail = hip.tail
            pelvis.roll = hip.roll
            pelvis.parent = hip
            lThigh = rig.data.edit_bones["lThigh"]
            rThigh = rig.data.edit_bones["rThigh"]
            lThigh.parent = pelvis
            rThigh.parent = pelvis
        BlenderStatic.set_mode('OBJECT')

    def fixCustomShape(self, rig, bnames, factor, offset=0):
        from daz_import.figure import setCustomShapeScale
        for bname in bnames:
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                if pb.custom_shape:
                    setCustomShapeScale(pb, factor)
                    if offset:
                        for v in pb.custom_shape.data.vertices:
                            v.co += offset
                return

    def fixHands(self, rig):
        BlenderStatic.set_mode('EDIT')
        for suffix in [".L", ".R"]:
            forearm = rig.data.edit_bones["forearm"+suffix]
            hand = rig.data.edit_bones["hand"+suffix]
            hand.head = forearm.tail
            flen = (forearm.tail - forearm.head).length
            vec = hand.tail - hand.head
            hand.tail = hand.head + 0.35*flen/vec.length*vec

    def fixCarpals(self, rig):
        Carpals = {
            "Carpal1": "Index1",
            "Carpal2": "Mid1",
            "Carpal3": "Ring1",
            "Carpal4": "Pinky1",
        }

        if "lCarpal3" in rig.data.bones.keys():
            return
        BlenderStatic.set_mode('EDIT')
        for prefix in ["l", "r"]:
            for bname in ["Carpal1", "Carpal2"]:
                if prefix+bname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones[prefix+bname]
                    rig.data.edit_bones.remove(eb)
            hand = rig.data.edit_bones[prefix+"Hand"]
            hand.tail = 2*hand.tail - hand.head
            for bname, cname in Carpals.items():
                if prefix+cname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones.new(prefix+bname)
                    child = rig.data.edit_bones[prefix+cname]
                    eb.head = hand.head
                    eb.tail = child.head
                    eb.roll = child.roll
                    eb.parent = hand
                    child.parent = eb
                    child.use_connect = True
        BlenderStatic.set_mode('OBJECT')
        for ob in rig.children:
            if ob.type == 'MESH':
                for prefix in ["l", "r"]:
                    for vgrp in ob.vertex_groups:
                        if vgrp.name == prefix+"Carpal2":
                            vgrp.name = prefix+"Carpal4"

    def fixKnees(self, rig):
        from daz_import.Elements.Bone import setRoll
        eps = 0.5
        BlenderStatic.set_mode('EDIT')
        for thigh, shin, zaxis in self.Knees:
            eb1 = rig.data.edit_bones[thigh]
            eb2 = rig.data.edit_bones[shin]
            hip = eb1.head
            knee = eb2.head
            ankle = eb2.tail
            dankle = ankle-hip
            vec = ankle-hip
            vec.normalize()
            dknee = knee-hip
            dmid = vec.dot(dknee)*vec
            offs = dknee-dmid
            if offs.length/dknee.length < eps:
                knee = hip + dmid + zaxis*offs.length
                xaxis = zaxis.cross(vec)
            else:
                xaxis = vec.cross(dknee)
                xaxis.normalize()

            eb1.tail = eb2.head = knee
            setRoll(eb1, xaxis)
            eb2.roll = eb1.roll

    def fixBoneDrivers(self, rig, assoc0):
        def changeTargets(rna, rig):
            if rna.animation_data:
                drivers = list(rna.animation_data.drivers)
                print("    (%s %d)" % (rna.name, len(drivers)))
                for n, fcu in enumerate(drivers):
                    self.changeTarget(fcu, rna, rig, assoc)

        def getFinDrivers(amt):
            drivers = {}
            if amt.animation_data:
                for fcu in amt.animation_data.drivers:
                    prop = fcu.data_path[2:-2]
                    if UtilityBoneStatic.is_final(prop) or UtilityBoneStatic.is_rest(prop):
                        raw = PropsStatic.base(prop)
                        drivers[raw] = fcu
            return drivers

        assoc = dict([(bname, bname) for bname in rig.data.bones.keys()])
        for dname, bname in assoc0.items():
            assoc[dname] = bname
        drivers = getFinDrivers(rig.data)
        print("    (%s %d)" % (rig.data.name, len(drivers)))
        for fcu in drivers.values():
            self.changeTarget(fcu, rig.data, rig, assoc)
        #changeTargets(rig, rig)
        for ob in rig.children:
            changeTargets(ob, rig)
            if ob.type == 'MESH' and ob.data.shape_keys:
                changeTargets(ob.data.shape_keys, rig)

    def changeTarget(self, fcu, rna, rig, assoc):
        channel = fcu.data_path
        idx = self.getArrayIndex(fcu)
        fcu2 = self.getTmpDriver(0)
        self.copyFcurve(fcu, fcu2)
        if idx >= 0:
            rna.driver_remove(channel, idx)
        else:
            rna.driver_remove(channel)
        success = True
        for var in fcu2.driver.variables:
            for trg in var.targets:
                if trg.id_type == 'OBJECT':
                    trg.id = rig
                elif trg.id_type == 'ARMATURE':
                    trg.id = rig.data
                if var.type == 'TRANSFORMS':
                    bname = trg.bone_target
                    defbone = "DEF-" + bname
                    if bname in assoc.keys():
                        trg.bone_target = assoc[bname]
                    elif defbone in rig.pose.bones.keys():
                        trg.bone_target = defbone
                    else:
                        success = False
        if success:
            fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
            fcu3.data_path = channel
            if idx >= 0:
                fcu3.array_index = idx
        self.clearTmpDriver(0)

    def changeAllTargets(self, ob, rig, newrig):
        if ob.animation_data:
            for fcu in ob.animation_data.drivers:
                self.setId(fcu, rig, newrig)
        if ob.data.animation_data:
            for fcu in ob.data.animation_data.drivers:
                self.setId(fcu, rig, newrig)
        if ob.type == 'MESH':
            if ob.data.shape_keys and ob.data.shape_keys.animation_data:
                for fcu in ob.data.shape_keys.animation_data.drivers:
                    self.setId(fcu, rig, newrig)
            for mod in ob.modifiers:
                if mod.type == 'ARMATURE' and mod.object == rig:
                    mod.object = newrig

    def saveExistingRig(self, context):
        def dazName(string):
            return (string + "_DAZ")

        def dazifyName(ob):
            if ob.name[-4] == "." and ob.name[-3:].isdigit():
                return dazName(ob.name[:-4])
            else:
                return dazName(ob.name)

        def findChildrenRecursive(ob, objects):
            objects.append(ob)
            for child in ob.children:
                if not BlenderObjectStatic.is_hide(child):
                    findChildrenRecursive(child, objects)

        rig = context.object
        scn = context.scene
        BlenderStatic.activate(context, rig)
        objects = []
        findChildrenRecursive(rig, objects)
        for ob in objects:
            BlenderObjectStatic.select(ob, True)
        bpy.ops.object.duplicate()
        coll = bpy.data.collections.new(name=dazName(rig.name))
        mcoll = bpy.data.collections.new(name=dazName(rig.name) + " Meshes")
        scn.collection.children.link(coll)
        coll.children.link(mcoll)

        newObjects = BlenderStatic.selected(context)
        nrig = None
        for ob in newObjects:
            ob.name = dazifyName(ob)
            if ob.name == dazifyName(rig):
                nrig = ob
            BlenderStatic.unlink(ob)
            if ob.type == 'MESH':
                mcoll.objects.link(ob)
            else:
                coll.objects.link(ob)
        if nrig:
            for ob in newObjects:
                self.changeAllTargets(ob, rig, nrig)
        BlenderStatic.activate(context, rig)

    # -------------------------------------------------------------
    #   Face Bone
    # -------------------------------------------------------------

    def isFaceBone(self, pb):
        if pb.parent:
            par = pb.parent
            if par.name in ["upperFaceRig", "lowerFaceRig"]:
                return True
            elif (UtilityBoneStatic.is_drv_bone(par.name) and
                  par.parent and
                  par.parent.name in ["upperFaceRig", "lowerFaceRig"]):
                return True
        return False

    def isEyeLid(self, pb):
        return ("eyelid" in pb.name.lower())

    # -------------------------------------------------------------
    #   Gaze Bones
    # -------------------------------------------------------------

    def addSingleGazeBone(self, rig, suffix, headLayer, helpLayer):
        from daz_import.mhx import makeBone, deriveBone
        prefix = suffix[1].lower()
        eye = rig.data.edit_bones[prefix + "Eye"]
        eyegaze = deriveBone(prefix + "EyeGaze", eye,
                             rig, helpLayer, eye.parent)
        if UtilityBoneStatic.is_drv_bone(eye.parent.name):
            eyegaze.parent = eye.parent.parent
            eye.parent.parent = eyegaze
        else:
            eye.parent = eyegaze
        vec = eye.tail-eye.head
        vec.normalize()
        loc = eye.head + vec*rig.DazScale*30
        gaze = makeBone("gaze"+suffix, rig, loc, loc +
                        Vector((0, 5*rig.DazScale, 0)), 0, headLayer, None)

    def addCombinedGazeBone(self, rig, headLayer, helpLayer):
        from daz_import.mhx import makeBone, deriveBone
        lgaze = rig.data.edit_bones["gaze.L"]
        rgaze = rig.data.edit_bones["gaze.R"]
        head = rig.data.edit_bones["head"]
        loc = (lgaze.head + rgaze.head)/2
        gaze0 = makeBone("gaze0", rig, loc, loc +
                         Vector((0, 15*rig.DazScale, 0)), 0, helpLayer, head)
        gaze1 = deriveBone("gaze1", gaze0, rig, helpLayer, None)
        gaze = deriveBone("gaze", gaze0, rig, headLayer, gaze1)
        lgaze.parent = gaze
        rgaze.parent = gaze

    def addGazeConstraint(self, rig, suffix):
        from daz_import.mhx import setMhxProp, trackTo
        prop = "MhaGaze_" + suffix[1]
        setMhxProp(rig, prop, 1.0)
        prefix = suffix[1].lower()
        eyegaze = rig.pose.bones[prefix+"EyeGaze"]
        gaze = rig.pose.bones["gaze"+suffix]
        trackTo(eyegaze, gaze, rig, prop)

    def addGazeFollowsHead(self, rig):
        from daz_import.mhx import setMhxProp, copyTransform
        prop = "MhaGazeFollowsHead"
        setMhxProp(rig, prop, 1.0)
        gaze0 = rig.pose.bones["gaze0"]
        gaze1 = rig.pose.bones["gaze1"]
        copyTransform(gaze1, gaze0, rig, prop)

# -------------------------------------------------------------
#   Gizmos (custom shapes)
# -------------------------------------------------------------


class GizmoUser:
    def startGizmos(self, context, ob):
        from daz_import.Elements.Node import createHiddenCollection
        self.gizmos = {}
        self.hidden = createHiddenCollection(context, ob)

    def makeGizmos(self, gnames):
        self.makeEmptyGizmo("GZM_Circle", 'CIRCLE')
        self.makeEmptyGizmo("GZM_Ball", 'SPHERE')
        self.makeEmptyGizmo("GZM_Cube", 'CUBE')
        self.makeEmptyGizmo("GZM_Cone", 'CONE')

        from daz_import.Lib import Json
        folder = os.path.dirname(__file__)
        filepath = os.path.join(folder, "data", "gizmos.json")
        struct = Json.load(filepath)
        if gnames is None:
            gnames = struct.keys()
        for gname in gnames:
            if gname in bpy.data.meshes.keys():
                me = bpy.data.meshes[gname]
            else:
                gizmo = struct[gname]
                me = bpy.data.meshes.new(gname)
                me.from_pydata(gizmo["verts"], gizmo["edges"], [])
            self.makeGizmo(gname, me)

    def getOldGizmo(self, gname):
        for gname1 in self.hidden.objects.keys():
            if gname1.startswith(gname):
                ob = self.hidden.objects[gname1]
                self.gizmos[gname] = ob
                return ob
        return None

    def makeGizmo(self, gname, me, parent=None):
        ob = self.getOldGizmo(gname)
        if ob is not None:
            return ob
        ob = bpy.data.objects.new(gname, me)
        self.hidden.objects.link(ob)
        ob.parent = parent
        self.gizmos[gname] = ob
        ob.hide_render = True
        ob.hide_viewport = True
        return ob

    def makeEmptyGizmo(self, gname, dtype):
        ob = self.getOldGizmo(gname)
        if ob is not None:
            return ob
        empty = self.makeGizmo(gname, None)
        empty.empty_display_type = dtype
        return empty

    def addGizmo(self, pb, gname, scale, blen=None):
        from daz_import.figure import setCustomShapeScale
        gizmo = self.gizmos[gname]
        pb.custom_shape = gizmo
        pb.bone.show_wire = True
        if blen:
            setCustomShapeScale(pb, blen/pb.bone.length)
        else:
            setCustomShapeScale(pb, scale)

    def renameFaceBones(self, rig, extra=[]):
        def renameFaceBone(bone):
            bname = bone.name
            newname = getSuffixName(bname)
            if newname:
                renamed[bname] = newname
                bone.name = newname

        if not self.useRenameBones:
            return
        renamed = {}
        for pb in rig.pose.bones:
            if (self.isFaceBone(pb) or
                    pb.name[1:] in extra):
                renameFaceBone(pb.bone)
        for pb in rig.pose.bones:
            for cns in pb.constraints:
                if (hasattr(cns, "subtarget") and
                        cns.subtarget in renamed.keys()):
                    cns.subtarget = renamed[cns.subtarget]


def getSuffixName(bname):
    if UtilityBoneStatic.is_drv_bone(bname) or UtilityBoneStatic.is_final(bname):
        return None
    if len(bname) >= 2 and bname[1].isupper():
        if bname[0] == "r":
            return "%s%s.R" % (bname[1].lower(), bname[2:])
        elif bname[0] == "l":
            return "%s%s.L" % (bname[1].lower(), bname[2:])
    elif bname[0].isupper():
        return "%s%s" % (bname[0].lower(), bname[1:])
    return None

# -------------------------------------------------------------
#   Replace left-right prefix with suffix
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_ChangePrefixToSuffix(DazOperator, GizmoUser, IsArmature):
    bl_idname = "daz.change_prefix_to_suffix"
    bl_label = "Change Prefix To Suffix"
    bl_description = "Change l/r prefix to .L/.R suffix,\nto use Blender symmetry tools"
    bl_options = {'UNDO'}

    useRenameBones = True

    def run(self, context):
        rig = context.object
        self.renameFaceBones(rig)
        rig.DazRig = ""

    def isFaceBone(self, pb):
        return True

# -------------------------------------------------------------
#   Constraints class
# -------------------------------------------------------------


ConstraintAttributes = [
    "type", "name", "mute", "target", "subtarget",
    "head_tail", "use_offset", "owner_space", "target_space",
    "use_x", "use_y", "use_z",
    "invert_x", "invert_y", "invert_z",
    "use_limit_x", "use_limit_y", "use_limit_z",
    "use_min_x", "use_min_y", "use_min_z",
    "use_max_x", "use_max_y", "use_max_z",
    "min_x", "min_y", "min_z",
    "max_x", "max_y", "max_z",
]


def copyConstraints(src, trg, rig=None):
    for scns in src.constraints:
        tcns = trg.constraints.new(scns.type)
        for attr in ConstraintAttributes:
            if (hasattr(scns, attr) and attr != "type"):
                setattr(tcns, attr, getattr(scns, attr))
        if rig and hasattr(tcns, "target"):
            tcns.target = rig


class ConstraintStore:
    def __init__(self):
        self.constraints = {}

    def storeConstraints(self, key, pb):
        clist = []
        for cns in pb.constraints:
            struct = {}
            for attr in ConstraintAttributes:
                if hasattr(cns, attr):
                    struct[attr] = getattr(cns, attr)
            clist.append(struct)
        if clist and key:
            self.constraints[key] = clist

    def storeAllConstraints(self, rig):
        for pb in rig.pose.bones:
            self.storeConstraints(pb.name, pb)
            self.removeConstraints(pb)

    def getFkBone(self, key, rig):
        if len(key) > 2 and key[-2] == ".":
            base, suffix = key[:-2], key[-1]
            bname = base + ".fk." + suffix
            if bname in rig.pose.bones.keys():
                return rig.pose.bones[bname]
            bname = base + "_fk." + suffix
            if bname in rig.pose.bones.keys():
                return rig.pose.bones[bname]
        if key in rig.pose.bones.keys():
            return rig.pose.bones[key]
        return None

    def restoreAllConstraints(self, rig):
        for key, clist in self.constraints.items():
            if key:
                pb = self.getFkBone(key, rig)
                if pb:
                    for struct in clist:
                        self.restoreConstraint(struct, pb)

    def restoreConstraints(self, key, pb, target=None):
        if key not in self.constraints.keys():
            return
        clist = self.constraints[key]
        for struct in clist:
            self.restoreConstraint(struct, pb, target)

    def restoreConstraint(self, struct, pb, target=None):
        cns = pb.constraints.new(struct["type"])
        for attr, value in struct.items():
            if attr != "type":
                setattr(cns, attr, value)
        if target and hasattr(cns, "target"):
            cns.target = target

    def removeConstraints(self, pb):
        for cns in list(pb.constraints):
            cns.driver_remove("influence")
            cns.driver_remove("mute")
            pb.constraints.remove(cns)

# -------------------------------------------------------------
#   BendTwist class
# -------------------------------------------------------------


class BendTwists:

    def deleteBendTwistDrvBones(self, rig):
        from daz_import.driver import removeBoneSumDrivers
        BlenderStatic.set_mode('OBJECT')
        btnames = []
        bnames = {}
        for bone in rig.data.bones:
            if UtilityBoneStatic.is_drv_bone(bone.name) or UtilityBoneStatic.is_final(bone.name):
                bname = UtilityBoneStatic.base(bone.name)
                if bname.endswith(("Bend", "Twist")):
                    btnames.append(bone.name)
                    bnames[bname] = True
        removeBoneSumDrivers(rig, bnames.keys())
        BlenderStatic.set_mode('EDIT')
        for bname in btnames:
            eb = rig.data.edit_bones[bname]
            for cb in eb.children:
                cb.parent = eb.parent
            rig.data.edit_bones.remove(eb)

    def getBendTwistNames(self, bname):
        words = bname.split(".", 1)
        if len(words) == 2:
            bendname = words[0] + "Bend." + words[1]
            twistname = words[0] + "Twist." + words[1]
        else:
            bendname = bname + "Bend"
            twistname = bname + "Twist"
        return bendname, twistname

    def joinBendTwists(self, rig, renames, keep=True):
        BlenderStatic.set_mode('POSE')
        hiddenLayer = 31*[False] + [True]
        rotmodes = {}
        for bname, tname, _stretch, _isShin in self.BendTwists:
            bendname, twistname = self.getBendTwistNames(bname)
            if not (bendname in rig.pose.bones.keys() and
                    twistname in rig.pose.bones.keys()):
                continue
            pb = rig.pose.bones[bendname]
            rotmodes[bname] = pb.DazRotMode
            self.storeConstraints(bname, pb)
            self.removeConstraints(pb)
            self.deleteBoneDrivers(rig, bendname)
            pb = rig.pose.bones[twistname]
            self.removeConstraints(pb)
            self.deleteBoneDrivers(rig, twistname)

        BlenderStatic.set_mode('EDIT')
        for bname, tname, _stretch, _isShin in self.BendTwists:
            bendname, twistname = self.getBendTwistNames(bname)
            if not (bendname in rig.data.edit_bones.keys() and
                    twistname in rig.data.edit_bones.keys()):
                continue
            eb = rig.data.edit_bones.new(bname)
            bend = rig.data.edit_bones[bendname]
            twist = rig.data.edit_bones[twistname]
            target = rig.data.edit_bones[tname]
            eb.head = bend.head
            bend.tail = twist.head
            eb.tail = twist.tail = target.head
            eb.roll = bend.roll
            eb.parent = bend.parent
            eb.use_deform = False
            eb.use_connect = bend.use_connect
            children = [eb for eb in bend.children if eb !=
                        twist] + list(twist.children)
            for child in children:
                child.parent = eb

        for bname3, bname2 in renames.items():
            eb = rig.data.edit_bones[bname3]
            eb.name = bname2

        BlenderStatic.set_mode('OBJECT')
        for bname, rotmode in rotmodes.items():
            if bname in rig.pose.bones.keys():
                pb = rig.pose.bones[bname]
                pb.DazRotMode = rotmode

        from daz_import.figure import copyBoneInfo
        for bname, tname, _stretch, _isShin in self.BendTwists:
            bendname, twistname = self.getBendTwistNames(bname)
            if not bendname in rig.data.bones.keys():
                continue
            srcbone = rig.pose.bones[bendname]
            trgbone = rig.pose.bones[bname]
            copyBoneInfo(srcbone, trgbone)

        BlenderStatic.set_mode('EDIT')
        for bname, tname, _stretch, _isShin in self.BendTwists:
            bendname, twistname = self.getBendTwistNames(bname)
            if bendname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[bendname]
                if keep:
                    eb.layers = hiddenLayer
                else:
                    rig.data.edit_bones.remove(eb)
            if twistname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[twistname]
                if keep:
                    eb.layers = hiddenLayer
                else:
                    rig.data.edit_bones.remove(eb)

        BlenderStatic.set_mode('OBJECT')
        for ob in rig.children:
            for bname, tname, _stretch, _isShin in self.BendTwists:
                bend, twist = self.getBendTwistNames(bname)
                self.joinVertexGroups(ob, bname, bend, twist)

    def deleteBoneDrivers(self, rig, bname):
        if bname in rig.data.bones.keys():
            path = 'pose.bones["%s"]' % bname
            for channel in ["location", "rotation_euler", "rotation_quaternion", "scale", "HdOffset"]:
                rig.driver_remove("%s.%s" % (path, channel))

    def joinVertexGroups(self, ob, bname, bend, twist):
        vgbend = vgtwist = None
        if bend in ob.vertex_groups.keys():
            vgbend = ob.vertex_groups[bend]
        if twist in ob.vertex_groups.keys():
            vgtwist = ob.vertex_groups[twist]
        if vgbend is None and vgtwist is None:
            return
        elif vgbend is None:
            vgtwist.name = bname
            return
        elif vgtwist is None:
            vgbend.name = bname
            return

        vgrp = ob.vertex_groups.new(name=bname)
        indices = [vgbend.index, vgtwist.index]
        for v in ob.data.vertices:
            w = 0.0
            for g in v.groups:
                if g.group in indices:
                    w += g.weight
            if w > 1e-4:
                vgrp.add([v.index], w, 'REPLACE')
        ob.vertex_groups.remove(vgbend)
        ob.vertex_groups.remove(vgtwist)

    def getSubBoneNames(self, bname):
        base, suffix = bname.split(".")
        bendname = "%s.bend.%s" % (base, suffix)
        twistname = "%s.twist.%s" % (base, suffix)
        return bendname, twistname

    def createBendTwists(self, rig):
        from daz_import.mhx import L_TWEAK, L_FIN, L_DEF
        defLayer = L_DEF*[False] + [True] + (31-L_DEF)*[False]
        finLayer = L_FIN*[False] + [True] + (31-L_FIN)*[False]
        tweakLayer = L_TWEAK*[False] + [True] + (31-L_TWEAK)*[False]
        BlenderStatic.set_mode('EDIT')

        for bname, _, _, _ in self.BendTwists:
            eb = rig.data.edit_bones[bname]
            vec = eb.tail - eb.head
            bendname, twistname = self.getSubBoneNames(bname)
            bend = rig.data.edit_bones.new(bendname)
            twist = rig.data.edit_bones.new(twistname)
            bend.head = eb.head
            bend.tail = twist.head = eb.head+vec/2
            twist.tail = eb.tail
            bend.roll = twist.roll = eb.roll
            bend.parent = eb.parent
            twist.parent = bend
            bend.use_connect = eb.use_connect
            twist.use_connect = True
            eb.use_deform = False
            if self.addTweakBones:
                btwkname = self.getTweakBoneName(bendname)
                ttwkname = self.getTweakBoneName(twistname)
                bendtwk = rig.data.edit_bones.new(btwkname)
                twisttwk = rig.data.edit_bones.new(ttwkname)
                bendtwk.head = bend.head
                bendtwk.tail = twisttwk.head = twist.head
                twisttwk.tail = twist.tail
                bendtwk.roll = twisttwk.roll = eb.roll
                bendtwk.parent = bend
                twisttwk.parent = twist
                bend.use_deform = twist.use_deform = False
                bendtwk.use_deform = twisttwk.use_deform = True
                bend.layers = twist.layers = finLayer
                bendtwk.layers = twisttwk.layers = defLayer
                bendtwk.layers[L_TWEAK] = twisttwk.layers[L_TWEAK] = True
                bvgname = btwkname
                tvgname = ttwkname
            else:
                bend.use_deform = twist.use_deform = True
                bend.layers = twist.layers = defLayer
                bvgname = bendname
                tvgname = twistname

            for ob in rig.children:
                if (ob.type == 'MESH' and
                        self.getVertexGroup(ob, bname)):
                    self.splitVertexGroup2(
                        ob, bname, bvgname, tvgname, eb.head, eb.tail)

    def getVertexGroup(self, ob, vgname):
        for vgrp in ob.vertex_groups:
            if vgrp.name == vgname:
                return vgrp
        return None

    def splitVertexGroup2(self, ob, bname, bend, twist, head, tail):
        vgrp = self.getVertexGroup(ob, bname)
        vgrp1 = ob.vertex_groups.new(name=bend)
        vgrp2 = ob.vertex_groups.new(name=twist)
        vec = tail-head
        vec /= vec.dot(vec)
        for v in ob.data.vertices:
            for g in v.groups:
                if g.group == vgrp.index:
                    x = vec.dot(v.co - head)
                    if x < 0:
                        vgrp1.add([v.index], g.weight, 'REPLACE')
                    elif x < 1:
                        vgrp1.add([v.index], g.weight*(1-x), 'REPLACE')
                        vgrp2.add([v.index], g.weight*(x), 'REPLACE')
                    elif x > 1:
                        vgrp2.add([v.index], g.weight, 'REPLACE')
        ob.vertex_groups.remove(vgrp)

    def splitVertexGroup(self, ob, vgname, bendname, twistname, head, tail):
        vgrp = self.getVertexGroup(ob, vgname)
        bend = ob.vertex_groups.new(name=bendname)
        twist = ob.vertex_groups.new(name=twistname)
        vec = tail-head
        vec /= vec.dot(vec)
        for v in ob.data.vertices:
            for g in v.groups:
                if g.group == vgrp.index:
                    x = vec.dot(v.co - head)
                    if x < 0:
                        x = 0
                    elif x > 1:
                        x = 1
                    bend.add([v.index], g.weight*(1-x), 'REPLACE')
                    twist.add([v.index], g.weight*x, 'REPLACE')
        ob.vertex_groups.remove(vgrp)

    def constrainBendTwists(self, rig):
        from daz_import.mhx import dampedTrack, copyRotation, stretchTo, addDriver, setMhxProp
        BlenderStatic.set_mode('POSE')
        gizmo = "GZM_Ball025"
        for bname, trgname, stretch, isShin in self.BendTwists:
            bendname, twistname = self.getSubBoneNames(bname)
            if not UtilityBoneStatic.has_pose_bones(rig, [bname, bendname, twistname]):
                continue
            pb = rig.pose.bones[bname]
            bend = rig.pose.bones[bendname]
            twist = rig.pose.bones[twistname]
            pb2 = rig.pose.bones[trgname]
            cns1 = dampedTrack(bend, pb2, rig)
            cns2 = copyRotation(twist, pb, rig, space='WORLD')
            if isShin:
                prop = "MhaDazShin_%s" % bname[-1]
                setMhxProp(rig, prop, False)
                addDriver(cns1, "mute", rig, prop, "x")
                addDriver(cns2, "mute", rig, prop, "x")
                cns3 = copyRotation(bend, pb, rig, space='WORLD')
                addDriver(cns3, "mute", rig, prop, "not(x)")
            if stretch:
                cns = stretchTo(bend, pb2, rig)
                cns = stretchTo(twist, pb2, rig)
            if self.addTweakBones:
                btwkname = self.getTweakBoneName(bendname)
                ttwkname = self.getTweakBoneName(twistname)
                bendtwk = rig.pose.bones[btwkname]
                twisttwk = rig.pose.bones[ttwkname]
                self.addGizmo(bendtwk, gizmo, 1, blen=10*rig.DazScale)
                self.addGizmo(twisttwk, gizmo, 1, blen=10*rig.DazScale)

# -------------------------------------------------------------
#   Add IK goals
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_AddIkGoals(DazPropsOperator, GizmoUser, IsArmature):
    bl_idname = "daz.add_ik_goals"
    bl_label = "Add IK goals"
    bl_description = "Add IK goals"
    bl_options = {'UNDO'}

    usePoleTargets: BoolProperty(
        name="Pole Targets",
        description="Add pole targets to the IK chains",
        default=False)

    hideBones: BoolProperty(
        name="Hide Bones",
        description="Hide all bones in the IK chains",
        default=False)

    lockBones: BoolProperty(
        name="Lock Bones",
        description="Lock all bones in the IK chains",
        default=False)

    disableBones: BoolProperty(
        name="Disable Bones",
        description="Disable all bones in the IK chains",
        default=False)

    fromRoots: BoolProperty(
        name="From Root Bones",
        description="Select IK chains from root bones",
        default=True)

    def draw(self, context):
        self.layout.prop(self, "fromRoots")
        self.layout.separator()
        self.layout.prop(self, "usePoleTargets")
        self.layout.prop(self, "hideBones")
        self.layout.prop(self, "lockBones")
        self.layout.prop(self, "disableBones")

    def ikGoalsFromSelected(self, rig):
        ikgoals = []
        for pb in rig.pose.bones:
            if pb.bone.select and not pb.children:
                clen = 0
                par = pb
                pbones = []
                while par and par.bone.select:
                    pbones.append(par)
                    clen += 1
                    par = par.parent
                if clen > 2:
                    root = pbones[-1]
                    pbones = pbones[:-1]
                    ikgoals.append((pb.name, clen-1, pbones, root))
        return ikgoals

    def ikGoalsFromRoots(self, rig):
        ikgoals = []
        for root in rig.pose.bones:
            if root.bone.select:
                clen = 0
                pbones = []
                pb = root
                while pb and len(pb.children) == 1:
                    pb = pb.children[0]
                    pbones.append(pb)
                    clen += 1
                if clen > 2:
                    ikgoals.append((pb.name, clen-1, pbones, root))
        return ikgoals

    def run(self, context):
        rig = context.object
        if self.fromRoots:
            ikgoals = self.ikGoalsFromRoots(rig)
        else:
            ikgoals = self.ikGoalsFromSelected(rig)

        BlenderStatic.set_mode('EDIT')
        for bname, clen, pbones, root in ikgoals:
            eb = rig.data.edit_bones[bname]
            goalname = self.combineName(bname, "Goal")
            goal = rig.data.edit_bones.new(goalname)
            goal.head = eb.tail
            goal.tail = 2*eb.tail - eb.head
            goal.roll = eb.roll
            if self.usePoleTargets:
                for n in range(clen//2):
                    eb = eb.parent
                polename = self.combineName(bname, "Pole")
                pole = rig.data.edit_bones.new(polename)
                pole.head = eb.head + eb.length * eb.x_axis
                pole.tail = eb.tail + eb.length * eb.x_axis
                pole.roll = eb.roll

        BlenderStatic.set_mode('OBJECT')
        self.startGizmos(context, rig)
        gzmBall = self.makeEmptyGizmo("GZM_Ball", 'SPHERE')
        gzmCube = self.makeEmptyGizmo("GZM_Cube", 'CUBE')
        gzmCone = self.makeEmptyGizmo("GZM_Cone", 'CONE')

        BlenderStatic.set_mode('POSE')
        for bname, clen, pbones, root in ikgoals:
            if bname not in rig.pose.bones.keys():
                continue
            pb = rig.pose.bones[bname]
            rmat = pb.bone.matrix_local
            root.custom_shape = gzmCube

            goalname = self.combineName(bname, "Goal")
            goal = rig.pose.bones[goalname]
            goal.rotation_mode = pb.rotation_mode
            goal.bone.use_local_location = True
            goal.matrix_basis = rmat.inverted() @ pb.matrix
            goal.custom_shape = gzmBall

            if self.usePoleTargets:
                pole = rig.pose.bones[polename]
                pole.rotation_mode = pb.rotation_mode
                pole.bone.use_local_location = True
                pole.matrix_basis = rmat.inverted() @ pb.matrix
                pole.custom_shape = gzmCone

            cns = BlenderStatic.constraint(pb, 'IK')
            if cns:
                pb.constraints.remove(cns)
            cns = pb.constraints.new('IK')
            cns.name = "IK"
            cns.target = rig
            cns.subtarget = goalname
            cns.chain_count = clen
            cns.use_location = True
            if self.usePoleTargets:
                cns.pole_target = rig
                cns.pole_subtarget = polename
                cns.pole_angle = 0*VectorStatic.D
                cns.use_rotation = False
            else:
                cns.use_rotation = True

            if self.hideBones:
                for pb in pbones:
                    pb.bone.hide = True
            if self.lockBones:
                for pb in pbones:
                    pb.lock_location = (True, True, True)
                    pb.lock_rotation = (True, True, True)
                    pb.lock_scale = (True, True, True)
            if self.disableBones:
                for pb in pbones:
                    pb.bone.hide_select = True

    def combineName(self, bname, string):
        if bname[-2:].lower() in [".l", ".r", "_l", "_r"]:
            return "%s%s%s" % (bname[:-2], string, bname[-2:])
        else:
            return "%s%s" % (bname, string)


# -------------------------------------------------------------
#   Add Winder
# -------------------------------------------------------------
@Registrar()
class DAZ_OT_AddWinders(DazPropsOperator, GizmoUser, IsArmature):
    bl_idname = "daz.add_winders"
    bl_label = "Add Winders"
    bl_description = "Add winders to selected posebones"
    bl_options = {'UNDO'}

    winderLayer: IntProperty(
        name="Winder Layer",
        description="Bone layer for the winder bones",
        min=1, max=32,
        default=1)

    windedLayer: IntProperty(
        name="Winded Layer",
        description="Bone layer for the winded bones",
        min=1, max=32,
        default=2)

    useLockLoc: BoolProperty(
        name="Lock Location",
        description="Lock winder location even if original bone is not locked",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "winderLayer")
        self.layout.prop(self, "windedLayer")
        self.layout.prop(self, "useLockLoc")

    def run(self, context):
        rig = context.object
        self.winderLayers = (self.winderLayer-1) * \
            [False] + [True] + (32-self.winderLayer)*[False]
        self.windedLayers = (self.windedLayer-1) * \
            [False] + [True] + (32-self.windedLayer)*[False]
        for pb in self.findPoseRoots(rig):
            self.addWinder(context, pb, rig)

    def findPoseRoots(self, rig):
        proots = {}
        for pb in rig.pose.bones:
            if pb.bone.select and len(pb.children) == 1:
                proots[pb.name] = pb
        removes = {}
        for proot in proots.values():
            pb = proot
            while len(pb.children) == 1:
                pb = pb.children[0]
                removes[pb.name] = True
            if len(pb.children) > 0:
                removes[proot.name] = True
        for bname in removes.keys():
            if bname in proots.keys():
                del proots[bname]
        return proots.values()

    def addWinder(self, context, pb, rig):
        from daz_import.mhx import copyRotation, copyScale, copyLocation
        bname = pb.name
        wname = "Wind"+bname
        self.startGizmos(context, rig)
        self.makeGizmos(["GZM_Knuckle"])
        gizmo = self.gizmos["GZM_Knuckle"]

        BlenderStatic.set_mode('EDIT')
        eb = rig.data.edit_bones[bname]
        tarb = rig.data.edit_bones.new(wname)
        tarb.head = eb.head
        tarb.tail = eb.tail
        tarb.roll = eb.roll
        tarb.parent = eb.parent
        tarb.layers = self.winderLayers
        n = 1
        length = eb.length
        while eb.children and len(eb.children) == 1:
            eb = eb.children[0]
            tarb.tail = eb.tail
            n += 1
            length += eb.length

        BlenderStatic.set_mode('POSE')
        winder = rig.pose.bones[wname]
        winder.custom_shape = gizmo
        winder.bone.show_wire = True
        winder.rotation_mode = pb.rotation_mode
        winder.matrix_basis = pb.matrix_basis
        winder.lock_location = pb.lock_location
        winder.lock_rotation = pb.lock_rotation
        winder.lock_scale = pb.lock_scale
        if self.useLockLoc:
            winder.lock_location = (True, True, True)

        infl = 2*pb.bone.length/length
        cns1 = copyRotation(pb, winder, rig)
        cns1.influence = infl
        cns2 = copyScale(pb, winder, rig)
        cns2.influence = infl
        if not self.useLockLoc:
            cns3 = copyLocation(pb, winder, rig)
            cns3.influence = infl
        pb.bone.layers = self.windedLayers
        while pb.children and len(pb.children) == 1:
            pb = pb.children[0]
            infl = 2*pb.bone.length/length
            cns1 = copyRotation(pb, winder, rig)
            cns1.use_offset = True
            cns1.influence = infl
            pb.bone.layers = self.windedLayers


# -------------------------------------------------------------
#   Retarget armature
# -------------------------------------------------------------
@Registrar()
class DAZ_OT_ChangeArmature(DazOperator, IsArmature):
    bl_idname = "daz.change_armature"
    bl_label = "Change Armature"
    bl_description = "Make the active armature the armature of selected meshes"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        subrigs = {}
        for ob in BlenderStatic.selected_meshes(context):
            mod = BlenderStatic.modifier(ob, 'ARMATURE')
            if mod:
                subrig = mod.object
                if subrig and subrig != rig:
                    subrigs[subrig.name] = subrig
                mod.object = rig
            if ob.parent and ob.parent_type == 'BONE':
                wmat = ob.matrix_world.copy()
                bname = ob.parent_bone
                ob.parent = rig
                ob.parent_type = 'BONE'
                ob.parent_bone = bname
                ob.matrix_world = wmat
            else:
                ob.parent = rig
        BlenderStatic.activate(context, rig)
        for subrig in subrigs.values():
            self.addExtraBones(subrig, rig)

    def addExtraBones(self, subrig, rig):
        extras = {}
        for bname in subrig.data.bones.keys():
            if bname not in rig.data.bones.keys():
                bone = subrig.data.bones[bname]
                if bone.parent:
                    pname = bone.parent.name
                else:
                    pname = None
                extras[bname] = (bone.head_local.copy(), bone.tail_local.copy(
                ), bone.matrix_local.copy(), list(bone.layers), pname)
        if extras:
            BlenderStatic.set_mode('EDIT')
            for bname, data in extras.items():
                eb = rig.data.edit_bones.new(bname)
                eb.head, eb.tail, mat, eb.layers, pname = data
                if pname is not None:
                    eb.parent = rig.data.edit_bones[pname]
                eb.matrix = mat
            BlenderStatic.set_mode('OBJECT')

# ----------------------------------------------------------
#   Initialize
# ----------------------------------------------------------
