import bpy
import math
from math import pi
from typing import Any, List, Tuple, Iterable
from mathutils import *

from daz_import.utils import *
from daz_import.Elements.Transform import Transform
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import *

from daz_import.Elements.Node import Node, Instance, setBoneTransform
from daz_import.fix import getSuffixName
from daz_import.Elements.Morph import buildBoneFormula
from daz_import.merge import GenesisToes
from daz_import.driver import isBoneDriven

from daz_import.Elements.Bone.data import *
from daz_import.Elements.Bone.tools import *


class BoneInstance(Instance):

    def __init__(self, fileref, node, struct):
        super().__init__(fileref, node, struct)

        from daz_import.figure import FigureInstance
                    
        if isinstance(self.parent, FigureInstance):
            self.figure = self.parent
        elif isinstance(self.parent, BoneInstance):
            self.figure = self.parent.figure

        self.translation = node.translation
        self.rotation = node.rotation
        self.scale = node.scale

        node.translation = []
        node.rotation = []
        node.scale = []

        self.name = self.node.name
        self.roll = 0.0
        self.useRoll = False
        self.axes = [0, 1, 2]
        self.flipped = [False, False, False]
        self.flopped = [False, False, False]
        self.isPosed = False
        self.isBuilt = False
        self.test = (self.name in [])

    def testPrint(self, hdr):
        if self.test:
            print(hdr, self.name, self.rotation_order, self.axes, self.flipped)

    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        fname = (self.figure.name if self.figure else None)
        return "<BoneInst %s N: %s F: %s T: %s P: %s R:%s>" % (self.id, self.node.name, fname, self.target, pname, self.rna)

    def parentObject(self, context, ob):
        pass

    def buildExtra(self, context):
        pass

    def finalize(self, context):
        pass

    def getHeadTail(self, center: Any, mayfit=True) -> Tuple[Any, Any, Any, Any, Any]:

        if mayfit and self.restdata:
            head, tail, orient, xyz, origin, wsmat = self.restdata
            #head = (cp - center)
            #tail = (ep - center)

            if orient:
                x, y, z, w = orient
                orient = Quaternion((-w, x, y, z)).to_euler()
            else:
                orient = Euler(self.attributes["orientation"]*VectorStatic.D)
                xyz = self.rotation_order
        else:
            head = (self.attributes["center_point"] - center)
            tail = (self.attributes["end_point"] - center)
            orient = Euler(self.attributes["orientation"]*VectorStatic.D)
            xyz = self.rotation_order
            wsmat = self.U3

        if (tail-head).length < 0.1:
            tail = head + Vector((0, 1, 0))

        return head, tail, orient, xyz, wsmat

    RX = Matrix.Rotation(pi/2, 4, 'X')
    FX = Matrix.Rotation(pi, 4, 'X')
    FZ = Matrix.Rotation(pi, 4, 'Z')

    def buildEdit(self, figure, figinst, rig: bpy.types.Object, parent, center, isFace) -> None:

        self.makeNameUnique(rig.data.edit_bones)

        head, tail, orient, xyz, wsmat = self.getHeadTail(center)

        eb = rig.data.edit_bones.new(self.name)

        figure.bones[self.name] = eb.name
        figinst.bones[self.name] = self

        if (head-tail).length < 1e-5:
            raise RuntimeError("BUG: buildEdit %s %s %s" %
                               (self.name, head, tail))
        eb.parent = parent
        eb.head = head = VectorStatic.scaled(head)
        eb.tail = tail = VectorStatic.scaled(tail)

        length = (head-tail).length
        omat = orient.to_matrix()
        lsmat = self.getLocalMatrix(wsmat, omat)

        if not eulerIsZero(lsmat.to_euler()):
            self.isPosed = True
        omat = omat.to_4x4()

        if Settings.zup:
            omat = self.RX @ omat
        flip = self.FX

        if not Settings.unflipped:
            omat, flip = self.flipAxes(omat, xyz)

        #  engetudouiti's fix for posed bones
        rmat = wsmat.to_4x4()

        if Settings.zup:
            rmat = self.RX @ rmat @ self.RX.inverted()

        if rmat.determinant() > 1e-4:
            omat = rmat.inverted() @ omat

        if Settings.unflipped:
            omat.col[3][0:3] = head
            eb.matrix = omat
        else:
            omat = self.flipBone(omat, head, tail, flip)
            self.testPrint("FBONE")
            omat.col[3][0:3] = head
            eb.matrix = omat
            self.correctRoll(eb, figure)

        self.correctLength(eb, length)

        if Settings.useConnectClose and parent:
            dist = parent.tail - eb.head
            if dist.length < 1e-4*Settings.scale_:
                eb.use_connect = True

        if self.name in ["upperFaceRig", "lowerFaceRig"]:
            isFace = True

        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child: BoneInstance
                child.buildEdit(figure, figinst, rig, eb, center, isFace)

        self.isBuilt = True

    def makeNameUnique(self, ebones: Dict[str, Any]) -> None:
        if self.name not in ebones.keys():
            return

        orig = self.name

        if len(self.name) < 2:
            self.name = "%s-1" % self.name

        while self.name in ebones.keys():
            if self.name[-2] == "-" and self.name[-1].isdigit():
                self.name = "%s-%d" % (self.name[:-2], 1+int(self.name[-1]))
            else:
                self.name = "%s-1" % self.name

        print("Bone name made unique: %s => %s" % (orig, self.name))

    def flipAxes(self, omat, xyz: str) -> Tuple[Any, Any]:

        if xyz == 'YZX':    #
            # Blender orientation: Y = twist, X = bend
            euler = Euler((0, 0, 0))
            flip = self.FX
            self.axes = [0, 1, 2]
            self.flipped = [False, False, False]
            self.flopped = [False, True, True]
        elif xyz == 'YXZ':
            # Apparently not used
            euler = Euler((0, pi/2, 0))
            flip = self.FZ
            self.axes = [2, 1, 0]
            self.flipped = [False, False, False]
            self.flopped = [False, False, False]
        elif xyz == 'ZYX':  #
            euler = Euler((pi/2, 0, 0))
            flip = self.FX
            self.axes = [0, 2, 1]
            self.flipped = [False, True, False]
            self.flopped = [False, False, False]
        elif xyz == 'XZY':  #
            euler = Euler((0, 0, pi/2))
            flip = self.FZ
            self.axes = [1, 0, 2]
            self.flipped = [False, False, False]
            self.flopped = [False, True, False]
        elif xyz == 'ZXY':
            # Eyes and eyelids
            euler = Euler((pi/2, 0, 0))
            flip = self.FZ
            self.axes = [0, 2, 1]
            self.flipped = [False, True, False]
            self.flopped = [False, False, False]
        elif xyz == 'XYZ':  #
            euler = Euler((pi/2, pi/2, 0))
            flip = self.FZ
            self.axes = [1, 2, 0]
            self.flipped = [True, True, True]
            self.flopped = [True, True, False]

        if self.test:
            print("AXES", self.name, xyz, self.axes)

        rmat = euler.to_matrix().to_4x4()
        omat = omat @ rmat

        return omat, flip

    def flipBone(self, omat, head, tail, flip) -> Any:
        vec = tail-head
        yaxis = Vector(omat.col[1][0:3])

        if vec.dot(yaxis) < 0:
            if self.test:
                print("FLOP", self.name)

            self.flipped = self.flopped
            return omat @ flip
        else:
            return omat

    def correctRoll(self, eb, figure) -> None:

        if eb.name in RollCorrection.keys():
            offset = RollCorrection[eb.name]
        elif (figure.rigtype in ["genesis1", "genesis2"] and
              eb.name in RollCorrectionGenesis.keys()):
            offset = RollCorrectionGenesis[eb.name]
        else:
            return

        roll = eb.roll + offset*VectorStatic.D
        if roll > pi:
            roll -= 2*pi
        elif roll < -pi:
            roll += 2*pi
        eb.roll = roll

        a = self.axes
        f = self.flipped
        i = a.index(0)
        j = a.index(1)
        k = a.index(2)

        if offset == 90:
            tmp = a[i]
            a[i] = a[k]
            a[k] = tmp
            tmp = f[i]
            f[i] = not f[k]
            f[k] = tmp
        elif offset == -90:
            tmp = a[i]
            a[i] = a[k]
            a[k] = tmp
            tmp = f[i]
            f[i] = not f[k]
            f[k] = tmp
        elif offset == 180:
            f[i] = not f[i]
            f[k] = not f[k]

    def correctLength(self, eb, length: int) -> None:
        vec = (eb.tail - eb.head).normalized()
        eb.tail = eb.head + length*vec

    def buildBoneProps(self, rig: bpy.types.Object, center) -> None:

        if self.name not in rig.data.bones.keys():
            return

        bone = rig.data.bones[self.name]
        bone.use_inherit_scale = True
        bone.DazOrient = self.attributes["orientation"]

        head, tail, orient, xyz, wsmat = self.getHeadTail(center)
        head0, tail0, orient0, xyz0, wsmat0 = self.getHeadTail(center, False)

        bone.DazHead = head
        bone.DazTail = tail
        bone.DazAngle = 0

        vec = VectorStatic.scaled_and_convert_vector(
            tail) - VectorStatic.scaled_and_convert_vector(head)
        vec0 = VectorStatic.scaled_and_convert_vector(
            tail0) - VectorStatic.scaled_and_convert_vector(head0)

        if vec.length > 0 and vec0.length > 0:
            vec /= vec.length
            vec0 /= vec0.length
            sprod = vec.dot(vec0)

            if sprod < 0.99:
                bone.DazAngle = math.acos(sprod)
                bone.DazNormal = vec.cross(vec0)

        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildBoneProps(rig, center)

    def buildFormulas(self, rig: bpy.types.Object, hide):

        if (self.node.formulaData.formulas and
                self.name in rig.pose.bones.keys()):
            pb = rig.pose.bones[self.name]
            pb.rotation_mode = self.getRotationMode(
                pb, self.isRotMorph(self.node.formulaData.formulas))

            errors = []
            buildBoneFormula(self.node, rig, errors)

        if hide or not self.channelsData.getValue(["Visible"], True):
            self.figure.hiddenBones[self.name] = True
            bone = rig.data.bones[self.name]
            bone.hide = True

        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildFormulas(rig, hide)

    def isRotMorph(self, formulas: Iterable) -> bool:
        for formula in formulas:
            formula: dict
            if ("output" in formula.keys() and
                    "?rotation" in formula["output"]):
                return True
        return False

    def findRoll(self, eb, figure, isFace: bool) -> None:

        if (self.getRollFromPlane(eb, figure)):
            return

        if self.name in RotateRoll.keys():
            rr = RotateRoll[self.name]
        elif isFace or self.name in ["lEye", "rEye"]:
            self.fixEye(eb)
            rr = -90
        elif self.name in GenesisToes["lToe"]:
            rr = -90
        elif self.name in GenesisToes["rToe"]:
            rr = 90
        elif self.name in FingerBones:
            if figure.rigtype == "genesis8":
                if self.name[0] == "l":
                    rr = 90
                else:
                    rr = -90
            else:
                rr = 180
        else:
            rr = 0

        nz = -1

        if self.name in ArmBones:
            nz = 2
        elif self.name in LegBones+ToeBones+FingerBones:
            nz = 0

        eb.roll = rr*VectorStatic.D

        if nz >= 0:
            mat = eb.matrix.copy()
            mat[nz][2] = 0
            mat.normalize()
            eb.matrix = mat

    def fixEye(self, eb) -> None:
        vec = eb.tail - eb.head
        y = Vector((0, -1, 0))

        if vec.dot(y) > 0.99*eb.length:
            eb.tail = eb.head + eb.length*y

    def getRollFromPlane(self, eb, figure) -> bool:
        try:
            xplane, zplane = Planes[eb.name]
        except KeyError:
            return False

        if (zplane and
            zplane in self.figure.planes.keys() and
            (figure.rigtype in ["genesis3", "genesis8"] or
             not xplane)):
            zaxis = self.figure.planes[zplane]
            setRoll(eb, zaxis)
            eb.roll += pi/2
            if eb.roll > pi:
                eb.roll -= 2*pi
            return True
        elif (xplane and
              xplane in self.figure.planes.keys()):
            xaxis = self.figure.planes[xplane]
            setRoll(eb, xaxis)
            return True
        else:
            return False

    def getRotationMode(self, pb, useEulers: bool) -> str:
        if Settings.unflipped:
            return self.rotation_order
        elif useEulers:
            return self.getDefaultMode(pb)
        elif Settings.useQuaternions and pb.name in SocketBones:
            return 'QUATERNION'
        else:
            return self.getDefaultMode(pb)

    def getDefaultMode(self, pb) -> str:
        if pb.name in RotationModes.keys():
            return RotationModes[pb.name]
        else:
            return 'YZX'

    def buildPose(self, figure, inFace, targets, missing) -> None:
        node = self.node
        rig = figure.rna

        if node.name not in rig.pose.bones.keys():
            return

        pb = rig.pose.bones[node.name]
        self.rna = pb

        if self.name != node.getName():
            pb.DazAltName = node.getName()
        if isBoneDriven(rig, pb):
            pb.rotation_mode = self.getRotationMode(pb, True)
            pb.bone.layers = [False, True] + 30*[False]
        else:
            pb.rotation_mode = self.getRotationMode(pb, False)

        pb.DazRotMode = self.rotation_order
        #pb.DazHeadLocal = pb.bone.head_local
        #pb.DazTailLocal = pb.bone.tail_local

        tchildren = self.targetTransform(pb, node, targets, rig)
        self.setRotationLockDaz(pb)
        self.setLocationLockDaz(pb)

        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildPose(figure, inFace, tchildren, missing)

    def targetTransform(self, pb, node, targets, rig) -> Dict:
        if Settings.fitFile_:
            return {}

        tname = getTargetName(node.name, rig)

        if tname and tname in targets.keys():
            tinst = targets[tname]
            tfm = Transform(
                trans=tinst.attributes["translation"],
                rot=tinst.attributes["rotation"])
            tchildren = tinst.children
        else:
            tinst = None
            tfm = Transform(
                trans=self.attributes["translation"],
                rot=self.attributes["rotation"])
            tchildren = {}

        setBoneTransform(tfm, pb)
        return tchildren

    def formulate(self, key: str, value: Any) -> None:
        if self.figure is None:
            return

        channel, comp = key.split("/")
        self.attributes[channel][VectorStatic.index(comp)] = value
        pb = self.rna
        node = self.node

        tfm = Transform(
            trans=self.attributes["translation"],
            rot=self.attributes["rotation"])

        setBoneTransform(tfm, pb)

    def getLocksLimits(self, pb, structs: Dict[int, Any]) -> Tuple[List, List, bool]:
        locks = [False, False, False]
        limits = [None, None, None]
        useLimits = False

        for idx, comp in enumerate(structs):
            if "locked" in comp.keys() and comp["locked"]:
                locks[idx] = True
            elif "clamped" in comp.keys() and comp["clamped"]:
                if comp["min"] == 0 and comp["max"] == 0:
                    locks[idx] = True
                else:
                    limits[idx] = (comp["min"], comp["max"])
                    if comp["min"] != -180 or comp["max"] != 180:
                        useLimits = True

        return locks, limits, useLimits

    IndexComp = {0: "x", 1: "y", 2: "z"}

    def setRotationLockDaz(self, pb) -> None:
        locks, limits, useLimits = self.getLocksLimits(pb, self.rotation)

        if pb.rotation_mode == 'QUATERNION':
            return

        if Settings.useLockRot:
            # DazRotLocks used to update lock_rotation
            for n, lock in enumerate(locks):
                idx = self.axes[n]
                pb.DazRotLocks[idx] = lock

            for n, lock in enumerate(locks):
                idx = self.axes[n]
                pb.lock_rotation[idx] = lock

        if Settings.useLimitRot and useLimits and not self.isPosed:
            cns = pb.constraints.new('LIMIT_ROTATION')
            cns.owner_space = 'LOCAL'

            for n, limit in enumerate(limits):
                idx = self.axes[n]

                if limit is None:
                    continue

                mind, maxd = limit
                minr = mind*VectorStatic.D

                if abs(minr) < 1e-4:
                    minr = 0
                maxr = maxd*VectorStatic.D

                if abs(maxr) < 1e-4:
                    maxr = 0

                if self.flipped[n]:
                    tmp = minr
                    minr = -maxr
                    maxr = -tmp

                xyz = self.IndexComp[idx]

                if self.test:
                    print("RRR", pb.name, n, limit,
                          self.flipped[n], xyz, minr, maxr)

                setattr(cns, "use_limit_%s" % xyz, True)
                setattr(cns, "min_%s" % xyz, minr)
                setattr(cns, "max_%s" % xyz, maxr)

                if Settings.displayLimitRot:
                    setattr(pb, "use_ik_limit_%s" % xyz, True)
                    setattr(pb, "ik_min_%s" % xyz, minr)
                    setattr(pb, "ik_max_%s" % xyz, maxr)

    def setLocationLockDaz(self, pb) -> None:
        locks, limits, useLimits = self.getLocksLimits(pb, self.translation)

        if Settings.useLockLoc:
            # DazLocLocks used to update lock_location

            for n, lock in enumerate(locks):
                idx = self.axes[n]
                pb.DazLocLocks[idx] = lock

            for n, lock in enumerate(locks):
                idx = self.axes[n]
                pb.lock_location[idx] = lock

        if Settings.useLimitLoc and useLimits:
            cns = pb.constraints.new('LIMIT_LOCATION')
            cns.owner_space = 'LOCAL'

            for n, limit in enumerate(limits):
                idx = self.axes[n]

                if limit is None:
                    continue

                mind, maxd = limit

                if self.flipped[n]:
                    tmp = mind
                    mind = -maxd
                    maxd = -tmp

                xyz = self.IndexComp[idx]

                if self.test:
                    print("LLL", pb.name, n, self.axes, limit,
                          self.flipped[n], xyz, mind, maxd)

                setattr(cns, "use_min_%s" % xyz, True)
                setattr(cns, "use_max_%s" % xyz, True)
                setattr(cns, "min_%s" % xyz, mind*Settings.scale_)
                setattr(cns, "max_%s" % xyz, maxd*Settings.scale_)
