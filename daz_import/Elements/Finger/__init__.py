import bpy
from daz_import.Lib.Registrar import Registrar
from daz_import.Lib.Errors.Is import IsMeshArmature
from daz_import.Lib.BlenderStatic import BlenderStatic


# 5670-13025-7459
FingerPrints = {
    "19296-38115-18872": "Genesis",
    "21556-42599-21098": "Genesis2-female",
    # "21556-42599-21098" : "Genesis2-male",
    "17418-34326-17000": "Genesis3-female",
    "17246-33982-16828": "Genesis3-male",
    "16556-32882-16368": "Genesis8-female",
    "16384-32538-16196": "Genesis8-male",
}

FingerPrintsHD = {
    "19296-38115-18872": ("Genesis", 0),
    "76283-151718-75488": ("Genesis", 1),
    "303489-605388-301952": ("Genesis", 2),

    "21556-42599-21098": ("Genesis2-female", 0),
    "85253-169556-84358": ("Genesis2-female", 1),
    "339167-676544-337432": ("Genesis2-female", 2),

    "17418-34326-17000": ("Genesis3-female", 0),
    "68744-136652-68000": ("Genesis3-female", 1),
    "273396-545304-272000": ("Genesis3-female", 2),

    "17246-33982-16828": ("Genesis3-male", 0),
    "68056-135276-67312": ("Genesis3-male", 1),
    "270644-539800-269248": ("Genesis3-male", 2),

    "16556-32882-16368": ("Genesis8-female", 0),
    "65806-131236-65472": ("Genesis8-female", 1),
    "262514-524360-261888": ("Genesis8-female", 2),
    "1048762-2096272-1047552": ("Genesis8-female", 3),

    "16384-32538-16196": ("Genesis8-male", 0),
    "65118-129860-64784": ("Genesis8-male", 1),
    "259762-518856-259136": ("Genesis8-male", 2),
    "1037754-2074256-1036544": ("Genesis8-male", 3),
}


def getFingerPrint(ob):
    if ob.type == 'MESH':
        return ("%d-%d-%d" % (len(ob.data.vertices), len(ob.data.edges), len(ob.data.polygons)))


def getFingeredCharacter(ob, useOrig, verbose=True):
    modded = False
    if ob is None:
        return None, None, "", False
    elif ob.type == 'MESH':
        finger = getFingerPrint(ob)
        if finger in FingerPrints.keys():
            char = FingerPrints[finger]
        elif useOrig and ob.data.DazFingerPrint in FingerPrints.keys():
            char = FingerPrints[ob.data.DazFingerPrint]
            modded = True
        else:
            if verbose:
                print("Did not find fingerprint", finger)
            char = ""
        return ob.parent, ob, char, modded

    elif ob.type == 'ARMATURE':
        for child in ob.children:
            if child.type == 'MESH':
                finger = getFingerPrint(child)
                if finger in FingerPrints.keys():
                    return ob, child, FingerPrints[finger], False
                elif useOrig and child.data.DazFingerPrint in FingerPrints.keys():
                    return ob, child, FingerPrints[child.data.DazFingerPrint], True
        #print("Found no recognized mesh type")
        return ob, None, "", False

    else:
        ob = ob.parent
        if ob and ob.type == 'ARMATURE':
            return getFingeredCharacter(ob, useOrig)
        return None, None, "", False


def isCharacter(ob):
    return getFingeredCharacter(ob, False, verbose=False)[2]


@Registrar()
class DAZ_OT_GetFingerPrint(bpy.types.Operator, IsMeshArmature):
    bl_idname = "daz.get_finger_print"
    bl_label = "Get Fingerprint"
    bl_description = "Get fingerprint of active character"

    def draw(self, context):
        for line in self.lines:
            self.layout.label(text=line)

    def execute(self, context):
        return{'FINISHED'}

    def invoke(self, context, event):
        ob = context.object
        self.lines = ["Fingerprint for %s" % ob.name]
        rig, mesh, char, modded = getFingeredCharacter(ob, False)
        if mesh:
            finger = getFingerPrint(mesh)
            mesh = mesh.name
        else:
            finger = None
        if rig:
            rig = rig.name
        self.lines += [
            ("  Rig: %s" % rig),
            ("  Mesh: %s" % mesh),
            ("  Character: %s" % char),
            ("  Fingerprint: %s" % finger)]
        for line in self.lines:
            print(line)
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


def getRigMeshes(context):
    ob = context.object
    if (ob.type == 'MESH' and
            ob.parent is None):
        return None, [ob]

    rig = None
    for ob in BlenderStatic.selected(context):
        if ob.type == 'ARMATURE':
            rig = ob
            break
        elif ob.type == 'MESH' and ob.parent and ob.parent.type == 'ARMATURE':
            rig = ob.parent
            break
    meshes = []
    if rig:
        for ob in rig.children:
            if ob.type == 'MESH':
                meshes.append(ob)
    return rig, meshes
