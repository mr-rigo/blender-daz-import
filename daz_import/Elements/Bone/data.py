
# -------------------------------------------------------------
#   Roll correction in DAZ Studio mode
# -------------------------------------------------------------

RollCorrection = {
    "lCollar": 180,
    "lShldr": -90,
    "lShldrBend": -90,
    "lShldrTwist": -90,
    "lHand": -90,
    "lThumb1": 180,
    "lThumb2": 180,
    "lThumb3": 180,

    "rCollar": 180,
    "rShldr": 90,
    "rShldrBend": 90,
    "rShldrTwist": 90,
    "rHand": 90,
    "rThumb1": 180,
    "rThumb2": 180,
    "rThumb3": 180,

    "lEar": -90,
    "rEar": 90,
}

RollCorrectionGenesis = {
    "lEye": 180,
    "rEye": 180,
}

SocketBones = [
    "lShldr", "lShldrBend",
    "rShldr", "rShldrBend",
    "lThigh", "lThighBend",
    "rThigh", "rThighBend",
]

RotationModes = {
    "lHand": "YXZ",
    "rHand": "YXZ",
}

# -------------------------------------------------------------
#   Roll tables in Legacy mode
# -------------------------------------------------------------

RotateRoll = {
    "lPectoral": -90,
    "rPectoral": 90,

    "upperJaw": 0,
    "lowerJaw": 0,

    "lFoot": -90,
    "lMetatarsals": -90,
    "lToe": -90,

    "rFoot": 90,
    "rMetatarsals": 90,
    "rToe": 90,

    "lShldr": 90,
    "lShldrBend": 90,
    "lShldrTwist": 90,
    "lForeArm": 0,
    "lForearmBend": 90,
    "lForearmTwist": 90,

    "rShldr": -90,
    "rShldrBend": -90,
    "rShldrTwist": -90,
    "rForeArm": 0,
    "rForearmBend": -90,
    "rForearmTwist": -90,
}

ZPerpendicular = {
    "lShldr": 2,
    "lShldrBend": 2,
    "lShldrTwist": 2,
    "lForeArm": 2,
    "lForearmBend": 2,
    "lForearmTwist": 2,

    "rShldr": 2,
    "rShldrBend": 2,
    "rShldrTwist": 2,
    "rForeArm": 2,
    "rForearmBend": 2,
    "rForearmTwist": 2,

    "lThigh": 0,
    "lThighBend": 0,
    "lThighTwist": 0,
    "lShin": 0,
    "lFoot": 0,
    "lMetatarsals": 0,
    "lToe": 0,

    "rThigh": 0,
    "rThighBend": 0,
    "rThighTwist": 0,
    "rShin": 0,
    "rFoot": 0,
    "rMetatarsals": 0,
    "rToe": 0,
}

BoneAlternatives = {
    "abdomen": "abdomenLower",
    "abdomen2": "abdomenUpper",
    "chest": "chestLower",
    "chest_2": "chestUpper",
    "neck": "neckLower",
    "neck_2": "neckUpper",

    "lShldr": "lShldrBend",
    "lForeArm": "lForearmBend",
    "lWrist": "lForearmTwist",
    "lCarpal2-1": "lCarpal2",
    "lCarpal2": "lCarpal4",

    "rShldr": "rShldrBend",
    "rForeArm": "rForearmBend",
    "rWrist": "rForearmTwist",
    "rCarpal2-1": "rCarpal2",
    "rCarpal2": "rCarpal4",

    "upperJaw": "upperTeeth",
    "tongueBase": "tongue01",
    "tongue01": "tongue02",
    "tongue02": "tongue03",
    "tongue03": "tongue04",
    "MidBrowUpper": "CenterBrow",

    "lLipCorver": "lLipCorner",
    "lCheekLowerInner": "lCheekLower",
    "lCheekUpperInner": "lCheekUpper",
    "lEyelidTop": "lEyelidUpper",
    "lEyelidLower_2": "lEyelidLowerInner",
    "lNoseBirdge": "lNasolabialUpper",

    "rCheekLowerInner": "rCheekLower",
    "rCheekUpperInner": "rCheekUpper",

    "lThigh": "lThighBend",
    "lBigToe2": "lBigToe_2",

    "rThigh": "rThighBend",
    "rBigToe2": "rBigToe_2",

    "Shaft 1": "shaft1",
    "Shaft 2": "shaft2",
    "Shaft 3": "shaft3",
    "Shaft 4": "shaft4",
    "Shaft 5": "shaft5",
    "Shaft5": "shaft5",
    "Shaft 6": "shaft6",
    "Shaft 7": "shaft7",
    "Left Testicle": "lTesticle",
    "Right Testicle": "rTesticle",
    "Scortum": "scrotum",
    "Legs Crease": "legsCrease",
    "Rectum": "rectum1",
    "Rectum 1": "rectum1",
    "Rectum 2": "rectum2",
    "Colon": "colon",
    "Root": "shaftRoot",
    "root": "shaftRoot",
}


ArmBones = [
    "lShldr", "lShldrBend", "lShldrTwist",
    "lForeArm", "lForearmBend", "lForearmTwist",

    "rShldr", "rShldrBend", "rShldrTwist",
    "rForeArm", "rForearmBend", "rForearmTwist",
]

LegBones = [
    "lThigh", "lThighBend", "lThighTwist",
    "lShin", "lFoot", "lMetatarsals", "lToe",

    "rThigh", "rThighBend", "rThighTwist",
    "rShin", "rFoot", "rMetatarsals", "rToe",
]

FingerBones = [
    "lHand",
    "lCarpal1", "lCarpal2", "lCarpal3", "lCarpal4",
    "lIndex1", "lIndex2", "lIndex3",
    "lMid1", "lMid2", "lMid3",
    "lRing1", "lRing2", "lRing3",
    "lPinky1", "lPinky2", "lPinky3",

    "rHand",
    "rCarpal1", "rCarpal2", "rCarpal3", "rCarpal4",
    "rIndex1", "rIndex2", "rIndex3",
    "rMid1", "rMid2", "rMid3",
    "rRing1", "rRing2", "rRing3",
    "rPinky1", "rPinky2", "rPinky3",
]

ToeBones = [
    "lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
    "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2",

    "rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
    "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2",
]

Planes = {
    "lShldr": ("lArm", ""),
    "lForeArm": ("lArm", ""),
    "lHand": ("", "lHand"),
    "lCarpal1": ("", "lHand"),
    "lCarpal2": ("", "lHand"),
    "lCarpal3": ("", "lHand"),
    "lCarpal4": ("", "lHand"),
    "lThumb1": ("lThumb", ""),
    "lThumb2": ("lThumb", ""),
    "lThumb3": ("lThumb", ""),
    "lIndex1": ("lIndex", "lHand"),
    "lIndex2": ("lIndex", "lHand"),
    "lIndex3": ("lIndex", "lHand"),
    "lMid1": ("lMid", "lHand"),
    "lMid2": ("lMid", "lHand"),
    "lMid3": ("lMid", "lHand"),
    "lRing1": ("lRing", "lHand"),
    "lRing2": ("lRing", "lHand"),
    "lRing3": ("lRing", "lHand"),
    "lPinky1": ("lPinky", "lHand"),
    "lPinky2": ("lPinky", "lHand"),
    "lPinky3": ("lPinky", "lHand"),

    "rShldr": ("rArm", ""),
    "rForeArm": ("rArm", ""),
    "rHand": ("", "rHand"),
    "rCarpal1": ("", "rHand"),
    "rCarpal2": ("", "rHand"),
    "rCarpal3": ("", "rHand"),
    "rCarpal4": ("", "rHand"),
    "rThumb1": ("rThumb", ""),
    "rThumb2": ("rThumb", ""),
    "rThumb3": ("rThumb", ""),
    "rIndex1": ("rIndex", "rHand"),
    "rIndex2": ("rIndex", "rHand"),
    "rIndex3": ("rIndex", "rHand"),
    "rMid1": ("rMid", "rHand"),
    "rMid2": ("rMid", "rHand"),
    "rMid3": ("rMid", "rHand"),
    "rRing1": ("rRing", "rHand"),
    "rRing2": ("rRing", "rHand"),
    "rRing3": ("rRing", "rHand"),
    "rPinky1": ("rPinky", "rHand"),
    "rPinky2": ("rPinky", "rHand"),
    "rPinky3": ("rPinky", "rHand"),
}