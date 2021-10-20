from random import random
from daz_import.Elements.Color import ColorStatic


SkinMaterials = {
    "eyelash": "Black",
    "eyelashes": "Black",
    "eyemoisture": "Invis",
    "lacrimal": "Invis",
    "lacrimals": "Invis",
    "cornea": "Invis",
    "tear": "Invis",
    "eyereflection": "Invis",

    "fingernail": "Red",
    "fingernails": "Red",
    "toenail": "Red",
    "toenails": "Red",
    "lip": "Red",
    "lips": "Red",
    "mouth": "Mouth",
    "tongue": "Mouth",
    "innermouth": "Mouth",
    "gums": "Mouth",
    "teeth": "Teeth",
    "pupil": "Black",
    "pupils": "Black",
    "sclera": "White",
    "iris": "Blue",
    "irises": "Blue",

    "skinface": "Skin",
    "face": "Skin",
    "head": "Skin",
    "ears": "Skin",
    "skinleg": "Skin",
    "legs": "Skin",
    "skintorso": "Skin",
    "torso": "Skin",
    "body": "Skin",
    "skinarm": "Skin",
    "arms": "Skin",
    "feet": "Skin",
    "skinhip": "Skin",
    "hips": "Skin",
    "shoulders": "Skin",
    "skinhand": "Skin",
    "hands": "Skin",
}


class MaterialStatic:
    _selector = []

    @staticmethod
    def setDiffuse(mat, color):
        mat.diffuse_color[0:3] = color[0:3]

    @staticmethod
    def checkSetting(attr, op, val, minval, first, header):
        negop = None
        eps = 1e-4

        if op == "=":
            if val != minval:
                negop = "!="
        elif op == ">":
            if isinstance(val, str):
                if int(val) < int(minval):
                    negop = "<"
            elif val < minval-eps:
                negop = "<"
        elif op == "<":
            if isinstance(val, str):
                if int(val) > int(minval):
                    negop = ">"
            elif val > minval+eps:
                negop = ">"

        if negop:
            msg = ("  %s: %s %s %s" % (attr, val, negop, minval))
            if first:
                print("%s:" % header)
            print(msg)

            return True, minval
        else:
            return False, minval

    @staticmethod
    def getSkinMaterial(mat):
        mname = mat.name.lower().split(
            "-")[0].split(".")[0].split(" ")[0].split("&")[0]

        if mname in SkinMaterials.keys():
            return SkinMaterials[mname]

        mname2 = mname.rsplit("_", 2)[-1]

        if mname2 in SkinMaterials.keys():
            return SkinMaterials[mname2]

        return None

    @classmethod
    def guessMaterialColor(cls, mat, choose, enforce, default):

        if (mat is None or
                not cls.hasDiffuseTexture(mat, enforce)):
            return

        elif choose == 'RANDOM':
            color = (random(), random(), random(), 1)
            cls.setDiffuse(mat, color)

        elif choose == 'GUESS':
            color = cls.getSkinMaterial(mat)
            if mat.diffuse_color[3] < 1.0:
                pass
            elif color is not None:
                if color == "Skin":
                    cls.setDiffuse(mat, default)
                elif color == "Red":
                    cls.setDiffuse(mat, (1, 0, 0, 1))
                elif color == "Mouth":
                    cls.setDiffuse(mat, (0.8, 0, 0, 1))
                elif color == "Blue":
                    cls.setDiffuse(mat, (0, 0, 1, 1))
                elif color == "Teeth":
                    cls.setDiffuse(mat, (1, 1, 1, 1))
                elif color == "White":
                    cls.setDiffuse(mat, (1, 1, 1, 1))
                elif color == "Black":
                    cls.setDiffuse(mat, (0, 0, 0, 1))
                elif color == "Invis":
                    cls.setDiffuse(mat, (0.5, 0.5, 0.5, 0))
            else:
                cls.setDiffuse(mat, default)

    @classmethod
    def hasDiffuseTexture(cls, mat, enforce):
        from daz_import.Elements.Color import ColorStatic

        if mat.node_tree:
            color = (1, 1, 1, 1)
            node = None
            for node1 in mat.node_tree.nodes.values():
                if node1.type == "BSDF_DIFFUSE":
                    node = node1
                    name = "Color"
                elif node1.type == "BSDF_PRINCIPLED":
                    node = node1
                    name = "Base Color"
                elif node1.type in ["HAIR_INFO", "BSDF_HAIR", "BSDF_HAIR_PRINCIPLED"]:
                    return False
            if node is None:
                return True
            color = node.inputs[name].default_value
            for link in mat.node_tree.links:
                if (link.to_node == node and
                        link.to_socket.name == name):
                    return True
            cls.setDiffuse(mat, color)
            return False
        else:
            if not ColorStatic.isWhite(mat.diffuse_color) and not enforce:
                return False
            for mtex in mat.texture_slots:
                if mtex and mtex.use_map_color_diffuse:
                    return True
            return False

    @classmethod
    def getMaterialSelector(cls):
        return cls._selector

    @classmethod
    def setMaterialSelector(cls, selector):
        cls._selector = selector
