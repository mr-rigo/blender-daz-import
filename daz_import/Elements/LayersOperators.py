
# import bpy
from daz_import.mhx import *
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import *

from daz_import.Lib import Registrar

MhxLayers = [
    ((L_MAIN,       'Root', 'MhxRoot'),
     (L_SPINE,     'Spine', 'MhxFKSpine')),
    ((L_HEAD,       'Head', 'MhxHead'),
     (L_FACE,       'Face', 'MhxFace')),
    ((L_TWEAK,      'Tweak', 'MhxTweak'),
     (L_CUSTOM,     'Custom', 'MhxCustom')),
    ('Left', 'Right'),
    ((L_LARMIK,     'IK Arm', 'MhxIKArm'),
     (L_RARMIK,     'IK Arm', 'MhxIKArm')),
    ((L_LARMFK,     'FK Arm', 'MhxFKArm'),
     (L_RARMFK,     'FK Arm', 'MhxFKArm')),
    ((L_LLEGIK,     'IK Leg', 'MhxIKLeg'),
     (L_RLEGIK,     'IK Leg', 'MhxIKLeg')),
    ((L_LLEGFK,     'FK Leg', 'MhxFKLeg'),
     (L_RLEGFK,     'FK Leg', 'MhxFKLeg')),
    ((L_LEXTRA,     'Extra', 'MhxExtra'),
     (L_REXTRA,     'Extra', 'MhxExtra')),
    ((L_LHAND,      'Hand', 'MhxHand'),
     (L_RHAND,      'Hand', 'MhxHand')),
    ((L_LFINGER,    'Fingers', 'MhxFingers'),
     (L_RFINGER,    'Fingers', 'MhxFingers')),
    ((L_LTOE,       'Toes', 'MhxToe'),
     (L_RTOE,       'Toes', 'MhxToe')),
]


@Registrar()
class DAZ_OT_MhxEnableAllLayers(DazOperator):
    bl_idname = "daz.pose_enable_all_layers"
    bl_label = "Enable all layers"
    bl_options = {'UNDO'}

    def run(self, context):
        # from daz_import.Elements.Finger import getRigMeshes
        from daz_import.Elements.Finger import getRigMeshes
        rig, _meshes = getRigMeshes(context)
        for (left, right) in MhxLayers:
            if type(left) != str:
                for (n, name, prop) in [left, right]:
                    rig.data.layers[n] = True


@Registrar()
class DAZ_OT_MhxDisableAllLayers(DazOperator):
    bl_idname = "daz.pose_disable_all_layers"
    bl_label = "Disable all layers"
    bl_options = {'UNDO'}

    def run(self, context):
        from daz_import.Elements.Finger import getRigMeshes

        rig, _meshes = getRigMeshes(context)
        layers = 32*[False]
        pb = context.active_pose_bone
        if pb:
            for n in range(32):
                if pb.bone.layers[n]:
                    layers[n] = True
                    break
        else:
            layers[0] = True
        if rig:
            rig.data.layers = layers

# ----------------------------------------------------------
#   Initialize
# ----------------------------------------------------------
