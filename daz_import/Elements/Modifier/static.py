import bpy
from daz_import.Lib.BlenderStatic import BlenderStatic

def stripPrefix(prop):
    lprop = prop.lower()
    for prefix in [
        "ectrlv", "ectrl", "pctrl", "ctrl",
        "phm", "ephm", "pbm", "ppbm", "vsm",
        "pjcm", "ejcm", "jcm", "mcm",
        "dzu", "dze", "dzv", "dzb", "facs_",
    ]:
        n = len(prefix)
        if lprop[0:n] == prefix:
            return prop[n:]
    return prop


def getCanonicalKey(key):
    key = stripPrefix(key)
    lkey = key.lower()
    if lkey[-5:] == "_div2":
        key = key[:-5]
        lkey = lkey[:-5]
    if lkey[-3:] == "_hd":
        key = key[:-3]
        lkey = lkey[:-3]
    if lkey[-2:] == "hd":
        key = key[:-2]
        lkey = lkey[:-2]
    if lkey[-4:-1] == "_hd":
        key = key[:-4] + key[-1]
        lkey = lkey[:-4] + lkey[-1]
    if lkey[-3:-1] == "hd":
        key = key[:-3] + key[-1]
        lkey = lkey[:-3] + lkey[-1]
    return key


def buildVertexGroup(ob, vgname, weights, default=None):
    if weights:
        if vgname in ob.vertex_groups.keys():
            print("Duplicate vertex group:\n  %s %s" % (ob.name, vgname))
            return ob.vertex_groups[vgname]
        else:
            vgrp = ob.vertex_groups.new(name=vgname)
        if default is None:
            for vn, w in weights:
                vgrp.add([vn], w, 'REPLACE')
        else:
            for vn in weights:
                vgrp.add([vn], default, 'REPLACE')
        return vgrp
    return None


def makeArmatureModifier(name, context, ob, rig):
    mod = ob.modifiers.new(name, 'ARMATURE')
    mod.object = rig
    mod.use_deform_preserve_volume = True
    BlenderStatic.activate(context, ob)
    for n in range(len(ob.modifiers)-1):
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    ob.location = (0, 0, 0)
    ob.rotation_euler = (0, 0, 0)
    ob.scale = (1, 1, 1)
    ob.lock_location = (True, True, True)
    ob.lock_rotation = (True, True, True)
    ob.lock_scale = (True, True, True)


def copyVertexGroups(ob, hdob):
    hdvgrps = {}
    for vgrp in ob.vertex_groups:
        hdvgrp = hdob.vertex_groups.new(name=vgrp.name)
        hdvgrps[vgrp.index] = hdvgrp
    for v in ob.data.vertices:
        vn = v.index
        for g in v.groups:
            hdvgrps[g.group].add([vn], g.weight, 'REPLACE')


def isModifiedMesh(ob):
    return (len(ob.data.DazOrigVerts) > 0)


def addShapekey(ob, sname):
    if not ob.data.shape_keys:
        basic = ob.shape_key_add(name="Basic")
    else:
        basic = ob.data.shape_keys.key_blocks[0]
    if sname in ob.data.shape_keys.key_blocks.keys():
        skey = ob.data.shape_keys.key_blocks[sname]
        ob.shape_key_remove(skey)
    return ob.shape_key_add(name=sname)

