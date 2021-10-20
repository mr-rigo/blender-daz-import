from mathutils import Matrix
from math import pi, atan
from typing import Any
import bpy

from daz_import.fix import getSuffixName
from daz_import.Elements.Bone.data import BoneAlternatives
from urllib.parse import unquote


def getTargetName(bname: str, rig: bpy.types.Object) -> Any:

    bname = unquote(bname)

    if bname in rig.pose.bones.keys():
        return bname

    altnames = dict([(pb.DazAltName, pb.name) for pb in rig.pose.bones])

    if bname in altnames.keys():
        return altnames[bname]
    elif (bname in BoneAlternatives.keys() and
          BoneAlternatives[bname] in rig.pose.bones.keys()):
        return BoneAlternatives[bname]

    sufname = getSuffixName(bname)

    if sufname and sufname in rig.pose.bones.keys():
        return sufname

    return None


def eulerIsZero(euler):
    vals = [abs(x) for x in euler]
    return (max(vals) < 1e-4)


def setRoll(eb, xaxis):
    yaxis = eb.tail - eb.head
    yaxis.normalize()
    xaxis -= yaxis.dot(xaxis)*yaxis
    xaxis.normalize()
    zaxis = xaxis.cross(yaxis)
    zaxis.normalize()
    eb.roll = getRoll(xaxis, yaxis, zaxis)


def getRoll(xaxis, yaxis, zaxis):
    mat: Matrix = Matrix().to_3x3()
    
    mat.col[0] = xaxis
    mat.col[1] = yaxis
    mat.col[2] = zaxis
    return getRollFromQuat(mat.to_quaternion())


def getRollFromQuat(quat):
    if abs(quat.w) < 1e-4:
        roll = pi
    else:
        roll = 2 * atan(quat.y / quat.w)
    return roll
