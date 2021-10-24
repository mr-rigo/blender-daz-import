import sys
import bpy

from mathutils import Vector
from math import floor

from daz_import.Lib.Settings import Settings
from daz_import.Lib.Errors import *
from daz_import.utils import *
from daz_import.Elements.Color import ColorStatic, ColorProp
from daz_import.Elements.Material.Cycles import CyclesShader
from daz_import.Elements.Material.Data import EnumsHair
from daz_import.Elements.Morph import Selector
from daz_import.Elements.Material.MaterialGroup import MaterialGroup

from .HairSystem import HairSystem


class CombineHair:

    def addStrands(self, hum, strands, hsystems, haircount):
        for strand in strands:
            mnum, n, strand = self.getStrand(strand)
            key, mnum = self.getHairKey(n, mnum)
            if key not in hsystems.keys():
                hsystems[key] = HairSystem(key, n, hum, mnum, self)
            hsystems[key].strands.append(strand)
        return len(strands)

    @staticmethod
    def combineHairSystems(hsystems, hsyss):
        for key, hsys in hsyss.items():
            if key in hsystems.keys():
                hsystems[key].strands += hsys.strands
            else:
                hsystems[key] = hsys

    def hairResize(self, size, hsystems, hum):
        print("Resize hair")
        nsystems = {}

        for hsys in hsystems.values():
            key, mnum = self.getHairKey(size, hsys.mnum)

            if key not in nsystems.keys():
                nsystems[key] = HairSystem(key, size, hum, hsys.mnum, self)
            nstrands = hsys.resize(size)
            nsystems[key].strands += nstrands

        return nsystems


class HairUpdater:

    def getAllSettings(self, psys):
        psettings = self.getSettings(psys.settings)
        hdyn = psys.use_hair_dynamics
        csettings = self.getSettings(psys.cloth.settings)
        return psettings, hdyn, csettings

    def setAllSettings(self, psys, data):
        psettings, hdyn, csettings = data
        self.setSettings(psys.settings, psettings)
        psys.use_hair_dynamics = hdyn
        self.setSettings(psys.cloth.settings, csettings)

    def getSettings(self, pset):
        settings = {}
        for key in dir(pset):
            attr = getattr(pset, key)
            if (key[0] == "_" or
                key in ["count"] or
                (key in ["material", "material_slot"] and
                 not self.affectMaterial)):
                continue
            if (
                isinstance(attr, int) or
                isinstance(attr, bool) or
                isinstance(attr, float) or
                isinstance(attr, str)
            ):
                settings[key] = attr
        return settings

    @classmethod
    def setSettings(self, pset, settings):
        for key, value in settings.items():
            if key in ["use_absolute_path_time"]:
                continue
            try:
                setattr(pset, key, value)
            except AttributeError:
                pass


class HairShader(CyclesShader):
    type = 'HAIR'

    def __init__(self, material, color):
        super().__init__(material)
        self.color = color
        self.root = Vector(color)
        self.tip = Vector(color)
        self.roottex = None
        self.tiptex = None

    def build(self):
        self.makeTree()
        self.buildLayer("")

    def initLayer(self):
        self.column = 4
        self.active = None
        self.buildBump()

    def addTexco(self, slot):
        super().addTexco(slot)
        self.info = self.addNode('ShaderNodeHairInfo', col=1)
        #self.texco = self.info.outputs["Intercept"]

    def buildOutput(self):
        self.column += 1
        output = self.addNode('ShaderNodeOutputMaterial')
        self.links.new(self.active.outputs[0], output.inputs['Surface'])

    def buildBump(self):
        strength = self.getValue(["Bump Strength"], 1)
        # if False and strength:
        #     bump = self.addNode("ShaderNodeBump", col=2)
        #     bump.inputs["Strength"].default_value = strength
        #     bump.inputs["Distance"].default_value = 0.1 * Settings.scale
        #     bump.inputs["Height"].default_value = 1
        #     self.normal = bump

    def linkTangent(self, node):
        self.links.new(
            self.info.outputs["Tangent Normal"], node.inputs["Tangent"])

    def linkBumpNormal(self, node):
        self.links.new(
            self.info.outputs["Tangent Normal"], node.inputs["Normal"])

    def addRamp(self, node, label, root, tip, endpos=1, slot="Color"):
        ramp = self.addNode('ShaderNodeValToRGB', col=self.column-2)
        ramp.label = label
        self.links.new(self.info.outputs["Intercept"], ramp.inputs['Fac'])
        ramp.color_ramp.interpolation = 'LINEAR'
        colramp = ramp.color_ramp
        elt = colramp.elements[0]
        elt.position = 0
        if len(root) == 3:
            elt.color = list(root) + [1]
        else:
            elt.color = root
        elt = colramp.elements[1]
        elt.position = endpos
        if len(tip) == 3:
            elt.color = list(tip) + [0]
        else:
            elt.color = tip
        if node:
            node.inputs[slot].default_value[0:3] == root
        return ramp

    def readColor(self, factor):
        root, self.roottex = self.getColorTex(
            ["Hair Root Color"], "COLOR", self.color, useFactor=False)
        tip, self.tiptex = self.getColorTex(
            ["Hair Tip Color"], "COLOR", self.color, useFactor=False)
        self.material.rna.diffuse_color[0:3] = root
        self.root = factor * Vector(root)
        self.tip = factor * Vector(tip)

    def linkRamp(self, ramp, texs, node, slot):
        src = ramp
        for tex in texs:
            if tex:
                mix = self.addNode("ShaderNodeMixRGB", col=self.column-1)
                mix.blend_type = 'MULTIPLY'
                mix.inputs[0].default_value = 1.0
                self.links.new(tex.outputs[0], mix.inputs[1])
                self.links.new(ramp.outputs[0], mix.inputs[2])
                src = mix
                break
        self.links.new(src.outputs[0], node.inputs[slot])
        return src

    @staticmethod
    def setRoughness(diffuse, rough):
        diffuse.inputs["Roughness"].default_value = rough

    def mixSockets(self, socket1, socket2, weight):
        mix = self.addNode('ShaderNodeMixShader')
        mix.inputs[0].default_value = weight
        self.links.new(socket1, mix.inputs[1])
        self.links.new(socket2, mix.inputs[2])
        return mix

    def mixShaders(self, node1, node2, weight):
        return self.mixSockets(node1.outputs[0], node2.outputs[0], weight)

    def addShaders(self, node1, node2):
        add = self.addNode('ShaderNodeAddShader')
        self.links.new(node1.outputs[0], add.inputs[0])
        self.links.new(node2.outputs[0], add.inputs[1])
        return add


class FadeGroupShader(HairShader):
    def __init__(self):
        self.mat_group: MaterialGroup = MaterialGroup(self)
        self.mat_group.insockets += ["Shader", "Intercept", "Random"]
        self.mat_group.outsockets += ["Shader"]
        self.info = None

    def create(self, node, name, parent):
        HairShader.__init__(self, parent.material, ColorStatic.BLACK)
        self.mat_group.create(node, name, parent, 4)
        self.group.inputs.new("NodeSocketShader", "Shader")
        self.group.inputs.new("NodeSocketFloat", "Intercept")
        self.group.inputs.new("NodeSocketFloat", "Random")
        self.group.outputs.new("NodeSocketShader", "Shader")

    def addNodes(self, args=None):
        self.column = 3
        self.info = self.inputs
        ramp = self.addRamp(None, "Root Transparency",
                            (1, 1, 1, 0), (1, 1, 1, 1), endpos=0.15)
        maprange = self.addNode('ShaderNodeMapRange', col=1)

        maprange.inputs["From Min"].default_value = 0
        maprange.inputs["From Max"].default_value = 1
        maprange.inputs["To Min"].default_value = -0.1
        maprange.inputs["To Max"].default_value = 0.4

        self.links.new(self.inputs.outputs["Random"], maprange.inputs["Value"])

        add = self.addSockets(
            ramp.outputs["Alpha"], maprange.outputs["Result"], col=2)
        transp = self.addNode('ShaderNodeBsdfTransparent', col=2)
        transp.inputs["Color"].default_value[0:3] = ColorStatic.WHITE
        mix = self.mixSockets(
            transp.outputs[0], self.inputs.outputs["Shader"], 1)
        self.links.new(add.outputs[0], mix.inputs[0])
        self.links.new(mix.outputs[0], self.outputs.inputs["Shader"])

    def addSockets(self, socket1, socket2, col=None):
        node = self.addNode("ShaderNodeMath", col=col)
        math.operation = 'ADD'
        self.links.new(socket1, node.inputs[0])
        self.links.new(socket2, node.inputs[1])
        return node


class FadeHairShader(HairShader):

    def build(self, mat):
        from daz_import.Elements.Material.Cycles import findNode, findLinksTo

        if mat.node_tree is None:
            print("Material %s has no nodes" % mat.name)
            return
        elif findNode(mat.node_tree, "TRANSPARENCY"):
            print("Hair material %s already has fading roots" % mat.name)
            return

        self.recoverTree(mat)
        links = findLinksTo(self.shader_object, "OUTPUT_MATERIAL")
        if not links:
            return

        link = links[0]
        fade = self.addGroup(FadeGroupShader, "DAZ Fade Roots", col=5)
        
        self.links.new(link.from_node.outputs[0], fade.inputs["Shader"])
        self.links.new(
            self.info.outputs["Intercept"], fade.inputs["Intercept"])
        self.links.new(self.info.outputs["Random"], fade.inputs["Random"])

        for link in links:
            self.links.new(fade.outputs["Shader"], link.to_socket)

    def recoverTree(self, mat):
        from daz_import.Elements.Material.Cycles import findNode, YSIZE, NCOLUMNS
        
        self.shader_object = mat.node_tree
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        self.info = findNode(self.shader_object, "HAIR_INFO")

        for col in range(NCOLUMNS):
            self.ycoords[col] -= YSIZE

    @classmethod
    def addFade(cls, mat):
        tree = cls(mat, mat.diffuse_color[0:3])
        tree.build(mat)


class HairPBRShader(HairShader):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.216)
        pbr = self.active = self.addNode("ShaderNodeBsdfHairPrincipled")
        ramp = self.addRamp(pbr, "Color", self.root, self.tip)
        self.linkRamp(ramp, [self.roottex, self.tiptex], pbr, "Color")
        pbr.inputs["Roughness"].default_value = 0.2
        pbr.inputs["Radial Roughness"].default_value = 0.8
        pbr.inputs["IOR"].default_value = 1.1
        self.buildOutput()


class HairBSDFShader(HairShader):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.5)
        trans = self.buildTransmission()
        refl = self.buildHighlight()
        self.column += 1
        if trans and refl:
            #weight = self.getValue(["Highlight Weight"], 0.11)
            weight = self.getValue(["Glossy Layer Weight"], 0.5)
            self.active = self.mixShaders(trans, refl, weight)
        # self.buildAnisotropic()
        self.buildCutout()
        self.buildOutput()

    def buildTransmission(self):
        root, roottex = self.getColorTex(
            ["Root Transmission Color"], "COLOR", self.color, useFactor=False)
        tip, tiptex = self.getColorTex(
            ["Tip Transmission Color"], "COLOR", self.color, useFactor=False)
        trans = self.addNode('ShaderNodeBsdfHair')
        trans.component = 'Transmission'
        trans.inputs['Offset'].default_value = 0
        trans.inputs["RoughnessU"].default_value = 1
        trans.inputs["RoughnessV"].default_value = 1
        ramp = self.addRamp(trans, "Transmission", root, tip)
        self.linkRamp(ramp, [roottex, tiptex], trans, "Color")
        # self.linkTangent(trans)
        self.active = trans
        return trans

    def buildHighlight(self):
        refl = self.addNode('ShaderNodeBsdfHair')
        refl.component = 'Reflection'
        refl.inputs['Offset'].default_value = 0
        refl.inputs["RoughnessU"].default_value = 0.02
        refl.inputs["RoughnessV"].default_value = 1.0
        ramp = self.addRamp(refl, "Reflection", self.root, self.tip)
        self.linkRamp(ramp, [self.roottex, self.tiptex], refl, "Color")
        self.active = refl
        return refl

    def buildAnisotropic(self):
        # Anisotropic
        aniso = self.getValue(["Anisotropy"], 0)
        if aniso:
            if aniso > 0.2:
                aniso = 0.2
            node = self.addNode('ShaderNodeBsdfAnisotropic')
            self.links.new(self.rootramp.outputs[0], node.inputs["Color"])
            node.inputs["Anisotropy"].default_value = aniso
            arots = self.getValue(["Anisotropy Rotations"], 0)
            node.inputs["Rotation"].default_value = arots
            self.linkTangent(node)
            self.linkBumpNormal(node)
            self.column += 1
            self.active = self.addShaders(self.active, node)

    def buildCutout(self):
        # Cutout
        alpha = self.getValue(["Cutout Opacity"], 1)
        if alpha < 1:
            transp = self.addNode("ShaderNodeBsdfTransparent")
            transp.inputs["Color"].default_value[0:3] = ColorStatic.WHITE
            self.column += 1
            self.active = self.mixShaders(transp, self.active, alpha)
            self.material.setTransSettings(
                False, False, ColorStatic.WHITE, alpha)


class HairEeveeShader(HairShader):

    def buildLayer(self, uvname):
        self.initLayer()
        self.readColor(0.216)

        pbr = self.active = self.addNode("ShaderNodeBsdfPrincipled")
        self.ycoords[self.column] -= 500
        ramp = self.addRamp(pbr, "Color", self.root,
                            self.tip, slot="Base Color")
        self.linkRamp(ramp, [self.roottex, self.tiptex], pbr, "Base Color")
        pbr.inputs["Metallic"].default_value = 0.9
        pbr.inputs["Roughness"].default_value = 0.2
        self.buildOutput()


class Pinning:
    pinningX0: FloatProperty(
        name="Pin X0",
        min=0.0,
        max=1.0,
        default=0.25,
        precision=3,
        description=""
    )

    pinningX1: FloatProperty(
        name="Pin X1",
        min=0.0,
        max=1.0,
        default=0.75,
        precision=3,
        description=""
    )

    pinningW0: FloatProperty(
        name="Pin W0",
        min=0.0,
        max=1.0,
        default=1.0,
        precision=3,
        description=""
    )

    pinningW1: FloatProperty(
        name="Pin W1",
        min=0.0,
        max=1.0,
        default=0.0,
        precision=3,
        description=""
    )

    def pinCoeffs(self):
        x0 = self.pinningX0
        x1 = self.pinningX1
        w0 = self.pinningW0
        w1 = self.pinningW1
        k = (w1-w0)/(x1-x0)
        return x0, x1, w0, w1, k

    def draw(self, context):
        self.layout.prop(self, "pinningX0")
        self.layout.prop(self, "pinningX1")
        self.layout.prop(self, "pinningW0")
        self.layout.prop(self, "pinningW1")
