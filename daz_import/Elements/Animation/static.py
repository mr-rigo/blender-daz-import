import bpy
from mathutils import Vector
from typing import Dict

# -------------------------------------------------------------
#   Alias
# -------------------------------------------------------------


def getAlias(prop, rig):
    if prop in rig.DazAlias.keys():
        return rig.DazAlias[prop].s
    else:
        return prop


# -------------------------------------------------------------
#   Convert between frames and vectors
# -------------------------------------------------------------


def framesToVectors(frames: Dict) -> Dict:
    vectors = {}
    for idx in frames.keys():
        for t, y in frames[idx]:
            if t not in vectors.keys():
                vectors[t] = Vector((0, 0, 0))
            vectors[t][idx] = y
    return vectors


def vectorsToFrames(vectors: Dict) -> Dict:
    frames = {}
    for idx in range(3):
        frames[idx] = [[t, vectors[t][idx]] for t in vectors.keys()]
    return frames

# -------------------------------------------------------------
#   Combine bend and twist. Unused
# -------------------------------------------------------------


def combineBendTwistAnimations(anim: Dict, twists) -> None:
    for (bend, twist) in twists:
        if twist in anim.keys():
            if bend in anim.keys():
                addTwistFrames(anim[bend], anim[twist])
            else:
                anim[bend] = {"rotation": halfRotation(
                    anim[twist]["rotation"])}


def addTwistFrames(bframes: Dict, tframes: Dict) -> None:
    if "rotation" not in bframes:
        if "rotation" not in tframes:
            return bframes
        else:
            bframes["rotation"] = halfRotation(tframes["rotation"])
            return bframes
    elif "rotation" not in tframes:
        return bframes
    for idx in bframes["rotation"].keys():
        bkpts = dict(bframes["rotation"][idx])
        if idx in tframes["rotation"].keys():
            tkpts = tframes["rotation"][idx]
            for n, y in tkpts:
                if n in bkpts.keys():
                    bkpts[n] += y/2
                else:
                    bkpts[n] = y/2
        kpts = list(bkpts.items())
        kpts.sort()
        bframes["rotation"][idx] = kpts


def halfRotation(frames: Dict) -> Dict:
    nframes = {}
    for idx in frames.keys():
        nframes[idx] = [(n, y/2) for n, y in frames[idx]]
    return nframes

# -------------------------------------------------------------
#   Animations
# -------------------------------------------------------------


def extendFcurves(rig, frame0, frame1):
    act = rig.animation_data.action
    if act is None:
        return
    for fcu in act.fcurves:
        if fcu.keyframe_points:
            value = fcu.evaluate(frame0)
            print(fcu.data_path, fcu.array_index, value)
            for frame in range(frame0, frame1):
                fcu.keyframe_points.insert(frame, value, options={'FAST'})


def getChannel(url: str):
    words = url.split(":")
    if len(words) == 2:
        key = words[0]
    elif len(words) == 3:
        words = words[1].rsplit("/", 1)
        if len(words) == 2:
            key = words[1].rsplit("#")[-1]
        else:
            return None, None, None
    else:
        return None, None, None

    words = url.rsplit("?", 2)
    if len(words) != 2:
        return None, None, None
    words = words[1].split("/")
    if len(words) in [2, 3]:
        channel = words[0]
        comp = words[1]
        return key, channel, comp
    else:
        return None, None, None


def getAnimKeys(anim):
    return [key[0:2] for key in anim["keys"]]


# -------------------------------------------------------------
#   Save current frame
# -------------------------------------------------------------


def actionFrameName(ob, frame):
    return ("%s_%s" % (ob.name, frame))


def findAction(aname):
    for act in bpy.data.actions:
        if act.name == aname:
            return act
    return None
