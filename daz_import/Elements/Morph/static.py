import bpy
from mathutils import Vector
from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Lib.Errors import DazError
from daz_import.Lib.Utility import PropsStatic

import logging
from .data import *

# logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

morph_log = logging.getLogger('morph')
morph_log.setLevel(logging.DEBUG)

# FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
# logging.basicConfig(format=FORMAT)

MAX_EXPRESSION_SIZE = 255
MAX_TERMS = 12
MAX_TERMS2 = 9
MAX_EXPR_LEN = 240


def isPath(path):
    return (path[0:2] == '["')


def unPath(path):
    if path[0:2] == '["':
        return path[2:-2]
    elif path[0:6] == 'data["':
        return path[6, -2]
    else:
        return path


def getBoneVector(factor, comp, pb):
    from daz_import.Elements.Node import getTransformMatrix
    tmat = getTransformMatrix(pb)
    uvec = Vector((0, 0, 0))
    uvec[comp] = factor
    return uvec @ tmat


def getDrivenComp(vec):
    for n, x in enumerate(vec):
        if abs(x) > 0.1:
            return n, (1 if x >= 0 else -1), x


def getPrint(x):
    string = "%.3f" % x
    while (string[-1] == "0"):
        string = string[:-1]
    return string[:-1] if string[-1] == "." else string


def getMult(x, comp):
    xx = getPrint(x)
    if xx == "0":
        return "0"
    elif xx == "1":
        return comp
    elif xx == "-1":
        return "-" + comp
    else:
        return xx + "*" + comp


def getSign(u):
    if u < 0:
        return "-", -u
    else:
        return "+", u


def getUnit(path, rig):
    if path == "translation":
        return 1/rig.DazScale
    elif path == "rotation":
        return 1/VectorStatic.D
    else:
        return 1


def classifyShapekeys(ob, skeys):
    morphs = {}
    bodyparts = {}
    pgs = ob.data.DazBodyPart

    for skey in skeys.key_blocks[1:]:
        if skey.name in pgs.keys():
            item = pgs[skey.name]
            if item.s not in morphs.keys():
                morphs[item.s] = []
            morphs[item.s].append(skey.name)
            bodyparts[skey.name] = item.s
        else:
            bodyparts[skey.name] = "Custom"
    return bodyparts

# ------------------------------------------------------------------------
#   Apply morphs
# ------------------------------------------------------------------------


def getShapeKeyCoords(ob):
    coords = [v.co for v in ob.data.vertices]
    skeys = []
    if ob.data.shape_keys:
        for skey in ob.data.shape_keys.key_blocks[1:]:
            if abs(skey.value) > 1e-4:
                coords = [co + skey.value*(skey.data[n].co - ob.data.vertices[n].co)
                          for n, co in enumerate(coords)]
            skeys.append(skey)
    return skeys, coords


def applyMorphs(rig, props):
    for ob in rig.children:
        basic = ob.data.shape_keys.key_blocks[0]
        skeys, coords = getShapeKeyCoords(ob)
        for skey in skeys:
            path = 'key_blocks["%s"].value' % skey.name
            getDrivingProps(ob.data.shape_keys, path, props)
            ob.shape_key_remove(skey)
        basic = ob.data.shape_keys.key_blocks[0]
        ob.shape_key_remove(basic)
        for vn, co in enumerate(coords):
            ob.data.vertices[vn].co = co
    print("Morphs applied")


def getDrivingProps(rna, channel, props):
    if rna.animation_data:
        for fcu in rna.animation_data.drivers:
            for var in fcu.driver.variables:
                for trg in var.targets:
                    prop = trg.data_path.split('"')[1]
                    props[prop] = trg.id


def removeDrivingProps(rig, props):
    for prop, id in props.items():
        if rig == id:
            del rig[prop]
    for cat in rig.DazCategories:
        rig.DazCategories.remove(cat)


def buildBoneFormula(asset, rig, errors):
    from .LoadMorph import LoadMorph

    def buildChannel(exprs, pb, channel):
        lm = LoadMorph(rig, None)
        for idx, expr in exprs.items():
            factor = expr["factor"]
            driver = expr["bone"]
            path = expr["path"]
            comp = expr["comp"]
            unit = getUnit(path, rig)
            if factor and driver in rig.pose.bones.keys():
                pbDriver = rig.pose.bones[driver]
                if pbDriver.parent == pb:
                    print("Dependency loop: %s %s" % (pbDriver.name, pb.name))
                else:
                    uvec = getBoneVector(factor, comp, pbDriver)
                    dvec = getBoneVector(1.0, idx, pb)
                    idx2, sign, x = getDrivenComp(dvec)
                    lm.makeSimpleBoneDriver(
                        path, sign*uvec, pb, channel, idx2, driver, False)

    def buildValueDriver(exprs, raw):
        lm = LoadMorph(rig, None)
        for idx, expr in exprs.items():
            bname = expr["bone"]
            if (bname not in rig.pose.bones.keys() and
                    bname[-2:] == "-1"):
                bname = bname[:-2]
                print("TRY", bname)
            if bname not in rig.pose.bones.keys():
                print("Missing bone (buildValueDriver):", bname)
                continue
            final = PropsStatic.final(raw)
            if final not in rig.data.keys():
                rig.data[final] = 0.0
            lm.buildBoneDriver(raw, bname, expr, True)

    exprs = asset.formulaData.evalFormulas(rig, None)

    for driven, expr in exprs.items():
        expr: dict

        if rotation := expr.get("rotation"):
            if pb := rig.pose.bones.get(driven):
                buildChannel(rotation, pb, "rotation_euler")
        
        if translation := expr.get("translation"):
            if pb := rig.pose.bones.get(driven):
                buildChannel(translation, pb, "location")

        if value := expr.get("value"):
            buildValueDriver(value, driven)


# -------------------------------------------------------------
#   Morph sets
# -------------------------------------------------------------


def getMorphs0(ob, morphset, sets, category):
    if morphset == "All":
        return getMorphs0(ob, sets, None, category)
    elif isinstance(morphset, list):
        pgs = []
        for mset in morphset:
            pgs += getMorphs0(ob, mset, sets, category)
        return pgs
    elif sets is None or morphset in sets:
        if morphset == "Custom":
            if category:
                if isinstance(category, list):
                    cats = category
                elif isinstance(category, str):
                    cats = [category]
                else:
                    raise DazError(
                        "Category must be a string or list but got '%s'" % category)
                pgs = [cat.morphs for cat in ob.DazMorphCats if cat.name in cats]
            else:
                pgs = [cat.morphs for cat in ob.DazMorphCats]
            return pgs
        else:
            pg = getattr(ob, "Daz"+morphset)
            prunePropGroup(ob, pg, morphset)
            return [pg]
    else:
        raise DazError("BUG get_morphs: %s %s" % (morphset, sets))


def prunePropGroup(ob, pg, morphset):
    if morphset in theJCMMorphSets:
        return
    
    idxs = [n for n, item in enumerate(
        pg.values()) if item.name not in ob.keys()]
    
    if not idxs:
        return

    print("Prune", idxs, [item.name for item in pg.values()])
    idxs.reverse()

    for idx in idxs:
        pg.remove(idx)


def getAllLowerMorphNames(rig):
    props = []

    for cat in rig.DazMorphCats:
        props += [morph.name.lower() for morph in cat.morphs]

    for morphset in theStandardMorphSets:
        pg = getattr(rig, "Daz"+morphset)
        props += [prop.lower() for prop in pg.keys()]

    return [prop for prop in props if "jcm" not in prop]


def getMorphList(ob, morphset, sets=None):
    pgs = getMorphs0(ob, morphset, sets, None)
    mlist = []
    for pg in pgs:
        mlist += list(pg.values())
    mlist.sort()
    return mlist


def getMorphCategory(rig, prop):
    for cat in rig.DazMorphCats:
        if prop in cat.morphs.keys():
            return cat.name
    return "Shapes"


def getMorphsExternal(ob, morphset, category, activeOnly):
    def isActiveKey(key, rig):
        if rig:
            return (key in rig.DazActivated.keys() and
                    rig.DazActivated[key].active)
        else:
            return True

    if not isinstance(ob, bpy.types.Object):
        raise DazError(
            "get_morphs: First argument must be a Blender object, but got '%s'" % ob)
    morphset = morphset.capitalize()
    if morphset == "All":
        morphset = theMorphSets
    elif morphset not in theMorphSets:
        raise DazError("get_morphs: Morphset must be 'All' or one of %s, not '%s'" % (
            theMorphSets, morphset))
    pgs = getMorphs0(ob, morphset, None, category)
    mdict = {}
    rig = None

    if ob.type == 'ARMATURE':
        if activeOnly:
            rig = ob
        # if morphset in theJCMMorphSets:
        #    raise DazError("JCM morphs are stored in the mesh object")
        
        for pg in pgs:
            for key in pg.keys():
                if key in ob.keys() and isActiveKey(key, rig):
                    mdict[key] = ob[key]
                    
    elif ob.type == 'MESH':
        if activeOnly:
            rig = ob.parent
        # if morphset not in theJCMMorphSets:
        #    raise DazError("Only JCM morphs are stored in the mesh object")
        skeys = ob.data.shape_keys
        if skeys is None:
            return mdict
        for pg in pgs:
            for key in pg.keys():
                if key in skeys.key_blocks.keys() and isActiveKey(key, rig):
                    mdict[key] = skeys.key_blocks[key].value
    return mdict
