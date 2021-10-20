import bpy
from mathutils import Matrix, Vector, Euler
from daz_import.Lib.Settings import Settings, Settings
from daz_import.Lib.BlenderStatic import BlenderStatic
from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Lib.Utility import Updating


class NodeStatic:

    @staticmethod
    def copyElements(struct):
        nstruct = {}
        for key, value in struct.items():
            if isinstance(value, dict):
                nstruct[key] = value.copy()
            else:
                nstruct[key] = value
        return nstruct

    @staticmethod
    def addToCollection(ob, coll):
        if ob.name not in coll.objects:
            try:
                coll.objects.link(ob)
            except RuntimeError:
                pass
            #    print("Cannot link '%s' to '%s'" % (ob.name, coll.name))


def copyCollections(src, trg):
    for coll in bpy.data.collections:
        if (src.name in coll.objects and
                trg.name not in coll.objects):
            coll.objects.link(trg)


findLayerCollection = BlenderStatic.find_layer_collection
createHiddenCollection = BlenderStatic.createHiddenCollection


def setParent(context, ob, rig, bname=None, update=True):
    if update:
        Updating.scene(context)
    if ob.parent != rig:
        wmat = ob.matrix_world.copy()
        ob.parent = rig
        if bname:
            ob.parent_bone = bname
            ob.parent_type = 'BONE'
        else:
            ob.parent_type = 'OBJECT'
        BlenderStatic.world_matrix(ob, wmat)


def reParent(context, ob, rig):
    if ob.parent_type == 'BONE':
        bname = ob.parent_bone
    else:
        bname = None
    setParent(context, ob, rig, bname, False)


def clearParent(ob):
    wmat = ob.matrix_world.copy()
    ob.parent = None
    BlenderStatic.world_matrix(ob, wmat)


def getTransformMatrices(pb):
    dmat = Euler(Vector(pb.bone.DazOrient)*VectorStatic.D,
                 'XYZ').to_matrix().to_4x4()
    dmat.col[3][0:3] = VectorStatic.scaled_and_convert_vector(pb.bone.DazHead)

    parbone = pb.bone.parent
    if parbone and parbone.DazAngle != 0:
        rmat = Matrix.Rotation(parbone.DazAngle, 4, parbone.DazNormal)
    else:
        rmat = Matrix()

    if Settings.zup:
        bmat = Matrix.Rotation(-90*VectorStatic.D, 4,
                               'X') @ pb.bone.matrix_local
    else:
        bmat = pb.bone.matrix_local

    return dmat, bmat, rmat


def getTransformMatrix(pb):
    dmat, bmat, rmat = getTransformMatrices(pb)
    tmat = dmat.inverted() @ bmat
    return tmat.to_3x3()


def getBoneMatrix(tfm, pb, test=False):
    from daz_import.Elements.Transform import TransformStatic

    dmat, bmat, rmat = getTransformMatrices(pb)

    wmat = dmat @ tfm.getRotMat(pb) @ tfm.getScaleMat() @ dmat.inverted()
    wmat = rmat.inverted() @ tfm.getTransMat() @ rmat @ wmat
    mat = bmat.inverted() @ wmat @ bmat

    TransformStatic.roundMatrix(mat, 1e-4)

    if test:
        print("GGT", pb.name)
        print("VectorStatic.D", dmat)
        print("B", bmat)
        print("R", tfm.rotmat)
        print("RR", rmat)
        print("W", wmat)
        print("M", mat)

    return mat


def setBoneTransform(tfm, pb):
    mat = getBoneMatrix(tfm, pb)
    if tfm.trans is None or tfm.trans.length == 0.0:
        mat.col[3] = (0, 0, 0, 1)
    if tfm.hasNoScale():
        trans = mat.col[3].copy()
        mat = mat.to_quaternion().to_matrix().to_4x4()
        mat.col[3] = trans
    pb.matrix_basis = mat


def setBoneTwist(tfm, pb):
    mat = getBoneMatrix(tfm, pb)
    _, quat, _ = mat.decompose()
    euler = pb.matrix_basis.to_3x3().to_euler('YZX')
    euler.y += quat.to_euler('YZX').y
    if pb.rotation_mode == 'QUATERNION':
        pb.rotation_quaternion = euler.to_quaternion()
    else:
        pb.rotation_euler = euler


def isUnitMatrix(mat):
    diff = mat - Matrix()
    maxelt = max([abs(diff[i][j]) for i in range(3) for j in range(4)])
    return (maxelt < 0.01*Settings.scale_)  # Ignore shifts < 0.1 mm
