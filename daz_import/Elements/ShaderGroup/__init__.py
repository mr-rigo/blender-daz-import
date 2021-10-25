import bpy
from bpy.props import BoolProperty
from daz_import.Elements.Texture import Map
from daz_import.Elements.Material.Cycles import CyclesShader
from daz_import.Elements.Material.PbrTree import PBRShader
from daz_import.Elements.Material import MaterialGroup
from daz_import.Elements.Color import ColorStatic

from daz_import.Lib import Registrar
from daz_import.Lib.Settings import Settings
from daz_import.Lib.Errors import IsMesh, ErrorsStatic, DazPropsOperator, DazError


class ShaderGroup(CyclesShader):
    def __init__(self, mat=None):
        super().__init__(mat)
        self.mat_group = MaterialGroup(self)

    def create(self, node, name, parent, ncols):
        super().__init__(parent.material)
        self.mat_group.create(node, name, parent, ncols)

    def __repr__(self):
        return ("<NodeGroup %s>" % self.group)

    def in_sockets(self, *sockets: str):
        self.mat_group.insockets += sockets

    def out_sockets(self, *sockets: str):
        self.mat_group.outsockets += sockets

    def input(self, a: str, b: str):
        self.in_sockets(b)
        return self.group.inputs.new(a, b)

    def output(self, a: str, b: str):
        self.out_sockets(b)
        return self.group.outputs.new(a, b)

# ---------------------------------------------------------------------
#   Shell Group
# ---------------------------------------------------------------------


class ShellGroup:

    def __init__(self, push):
        self.group = None
        self.push = push

        self.mat_group = MaterialGroup(self)

    def create(self, node, name, parent):
        self.mat_group.create(node, name, parent, 10)

        self.input("NodeSocketFloat", "Influence")
        self.input("NodeSocketShader", "Cycles")
        self.input("NodeSocketShader", "Eevee")
        self.input("NodeSocketVector", "UV")
        self.input("NodeSocketFloat", "Displacement")
        self.output("NodeSocketShader", "Cycles")
        self.output("NodeSocketShader", "Eevee")
        self.output("NodeSocketFloat", "Displacement")

    def in_sockets(self, *sockets: str):
        self.mat_group.insockets += sockets

    def input(self, a: str, b: str):
        self.in_sockets(b)
        return self.group.inputs.new(a, b)

    def output(self, a: str, b: str):
        self.out_sockets(b)
        return self.group.outputs.new(a, b)

    def out_sockets(self, *sockets: str):
        self.mat_group.outsockets += sockets

    def addNodes(self, args):
        shmat, uvname = args
        shmat.rna = self.parent.material.rna

        self.material = shmat
        self.texco = self.inputs.outputs["UV"]
        self.buildLayer(uvname)

        alpha, tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)

        mult = self.add_node("ShaderNodeMath", 6)
        mult.operation = 'MULTIPLY'

        self.link(self.inputs.outputs["Influence"], mult.inputs[0])
        self.link_scalar(tex, mult, alpha, 1)

        transp = self.blacken()

        self.addOutput(mult, transp, self.cycles_socket(), "Cycles")
        self.addOutput(mult, transp, self.eevee_socket(), "Eevee")
        self.buildDisplacementNodes()

        if self.displacement:
            mult2 = self.add_node("ShaderNodeMath", 9)
            mult2.label = "Multiply Displacement"
            mult2.operation = 'MULTIPLY'

            self.link(mult.outputs[0], mult2.inputs[0])
            self.link(self.displacement, mult2.inputs[1])
            self.link(mult2.outputs[0],
                      self.outputs.inputs["Displacement"])
        else:
            self.link(
                self.inputs.outputs["Displacement"], self.outputs.inputs["Displacement"])


class OpaqueShellGroup(ShellGroup):
    def blacken(self):
        ...

    def addOutput(self, mult, _transp, socket, slot):
        mix = self.add_node("ShaderNodeMixShader", 8)
        mix.inputs[0].default_value = 1

        self.link(mult.outputs[0], mix.inputs[0])
        self.link(self.inputs.outputs[slot], mix.inputs[1])
        self.link(socket, mix.inputs[2])
        self.link(mix.outputs[0], self.outputs.inputs[slot])


class RefractiveShellGroup(ShellGroup):
    def blacken(self):
        transp = self.add_node("ShaderNodeBsdfTransparent", 7)
        transp.inputs[0].default_value[0:3] = ColorStatic.BLACK
                
        for node in self.shader_graph.nodes:
            if node.type == 'GROUP' and "Refraction Color" in node.inputs.keys():
                node.inputs["Refraction Color"].default_value[0:3] = ColorStatic.BLACK
                self.removeLink(node, "Refraction Color")
            elif node.type == 'BSDF_PRINCIPLED':
                node.inputs["Base Color"].default_value[0:3] = ColorStatic.BLACK
                self.removeLink(node, "Base Color")
                node.inputs["Transmission"].default_value = 0
                self.removeLink(node, "Transmission")
        return transp

    def addOutput(self, mult, transp, socket, slot):
        mix = self.add_node("ShaderNodeMixShader", 8)
        mix.inputs[0].default_value = 1
        self.link(mult.outputs[0], mix.inputs[0])
        self.link(transp.outputs[0], mix.inputs[1])
        self.link(socket, mix.inputs[2])
        add = self.add_node("ShaderNodeAddShader", 9)
        self.link(mix.outputs[0], add.inputs[0])
        self.link(self.inputs.outputs[slot], add.inputs[1])
        self.link(add.outputs[0], self.outputs.inputs[slot])


class OpaqueShellCyclesGroup(OpaqueShellGroup, CyclesShader):
    def create(self, node, name, parent):
        CyclesShader.__init__(self, parent.material)
        OpaqueShellGroup.create(self, node, name, parent)


class OpaqueShellPbrGroup(OpaqueShellGroup, PBRShader):
    def create(self, node, name, parent):
        PBRShader.__init__(self, parent.material)
        OpaqueShellGroup.create(self, node, name, parent)


class RefractiveShellCyclesGroup(RefractiveShellGroup, CyclesShader):
    def create(self, node, name, parent):
        CyclesShader.__init__(self, parent.material)
        RefractiveShellGroup.create(self, node, name, parent)


class RefractiveShellPbrGroup(RefractiveShellGroup, PBRShader):
    def create(self, node, name, parent):
        PBRShader.__init__(self, parent.material)
        RefractiveShellGroup.create(self, node, name, parent)


# ---------------------------------------------------------------------
#   Fresnel Group
# ---------------------------------------------------------------------

class FresnelShaderGroup(ShaderGroup):
    exponent = 0

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 4)
        self.input("NodeSocketFloat", "IOR")
        self.input("NodeSocketFloat", "Roughness")
        self.input("NodeSocketVector", "Normal")
        self.output("NodeSocketFloat", "Fac")

    def addNodes(self, args=None):
        geo = self.add_node("ShaderNodeNewGeometry", 0)

        divide = self.add_node("ShaderNodeMath", 1)
        divide.operation = 'DIVIDE'
        divide.inputs[0].default_value = 1.0
        self.link(self.inputs.outputs["IOR"], divide.inputs[1])

        if self.exponent:
            power = self.add_node("ShaderNodeMath", 1)
            power.operation = 'POWER'
            self.link(self.inputs.outputs["Roughness"], power.inputs[0])
            power.inputs[1].default_value = self.exponent

        bump = self.add_node("ShaderNodeBump", 1)
        self.link(self.inputs.outputs["Normal"], bump.inputs["Normal"])
        bump.inputs["Strength"].default_value = 0

        mix1 = self.add_node("ShaderNodeMixRGB", 2)
        self.link(geo.outputs["Backfacing"], mix1.inputs["Fac"])
        self.link(self.inputs.outputs["IOR"], mix1.inputs[1])
        self.link(divide.outputs["Value"], mix1.inputs[2])

        mix2 = self.add_node("ShaderNodeMixRGB", 2)
        if self.exponent:
            self.link(power.outputs[0], mix2.inputs["Fac"])
        else:
            self.link(
                self.inputs.outputs["Roughness"], mix2.inputs["Fac"])
        self.link(bump.outputs[0], mix2.inputs[1])
        self.link(geo.outputs["Incoming"], mix2.inputs[2])

        fresnel = self.add_node("ShaderNodeFresnel", 3)
        self.link(mix1.outputs[0], fresnel.inputs["IOR"])
        self.link(mix2.outputs[0], fresnel.inputs["Normal"])
        self.link(fresnel.outputs["Fac"], self.outputs.inputs["Fac"])


class UberFresnelShaderGroup(FresnelShaderGroup):
    exponent = 2


class PBRSkinFresnelShaderGroup(FresnelShaderGroup):
    exponent = 4

# ---------------------------------------------------------------------
#   Mix Group. Mixes Cycles and Eevee
# ---------------------------------------------------------------------


class MixShaderGroup(ShaderGroup):
    def __init__(self):
        super().__init__()

    def create(self, node, name, parent, ncols):
        super().create(node, name, parent, ncols)

        self.input("NodeSocketFloat", "Fac")
        self.input("NodeSocketShader", "Cycles")
        self.input("NodeSocketShader", "Eevee")
        self.output("NodeSocketShader", "Cycles")
        self.output("NodeSocketShader", "Eevee")

    def addNodes(self, args=None):
        self.mix1 = self.add_node("ShaderNodeMixShader", self.ncols-1)
        self.mix1.label = "Cycles"

        self.mix2 = self.add_node("ShaderNodeMixShader", self.ncols-1)
        self.mix2.label = "Eevee"

        self.link(self.inputs.outputs["Fac"], self.mix1.inputs[0])
        self.link(self.inputs.outputs["Fac"], self.mix2.inputs[0])
        self.link(self.inputs.outputs["Cycles"], self.mix1.inputs[1])
        self.link(self.inputs.outputs["Eevee"], self.mix2.inputs[1])
        self.link(self.mix1.outputs[0], self.outputs.inputs["Cycles"])
        self.link(self.mix2.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Add Group. Adds to Cycles and Eevee
# ---------------------------------------------------------------------


class AddShaderGroup(ShaderGroup):
    def __init__(self):
        self.add1 = None
        self.add2 = None
        super().__init__()

    def create(self, node, name, parent, ncols):
        super().create(node, name, parent, ncols)
        self.input("NodeSocketShader", "Cycles")
        self.input("NodeSocketShader", "Eevee")
        self.output("NodeSocketShader", "Cycles")
        self.output("NodeSocketShader", "Eevee")

    def addNodes(self, args=None):
        self.add1 = self.add_node("ShaderNodeAddShader", 2)
        self.add2 = self.add_node("ShaderNodeAddShader", 2)

        self.link(self.inputs.outputs["Cycles"], self.add1.inputs[0])
        self.link(self.inputs.outputs["Eevee"], self.add2.inputs[0])
        self.link(self.add1.outputs[0], self.outputs.inputs["Cycles"])
        self.link(self.add2.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Emission Group
# ---------------------------------------------------------------------


class EmissionShaderGroup(AddShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 3)
        self.input("NodeSocketColor", "Color")
        self.input("NodeSocketFloat", "Strength")

    def addNodes(self, args=None):
        super().addNodes(args)
        node = self.add_node("ShaderNodeEmission", 1)
        self.link(self.inputs.outputs["Color"], node.inputs["Color"])
        self.link(
            self.inputs.outputs["Strength"], node.inputs["Strength"])
        self.link(node.outputs[0], self.add1.inputs[1])
        self.link(node.outputs[0], self.add2.inputs[1])


class OneSidedShaderGroup(ShaderGroup):
    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 3)
        self.input("NodeSocketShader", "Cycles")
        self.input("NodeSocketShader", "Eevee")
        self.output("NodeSocketShader", "Cycles")
        self.output("NodeSocketShader", "Eevee")

    def addNodes(self, args=None):
        geo = self.add_node("ShaderNodeNewGeometry", 1)
        trans = self.add_node("ShaderNodeBsdfTransparent", 1)
        mix1 = self.add_node("ShaderNodeMixShader", 2)
        mix2 = self.add_node("ShaderNodeMixShader", 2)
        self.link(geo.outputs["Backfacing"], mix1.inputs[0])
        self.link(geo.outputs["Backfacing"], mix2.inputs[0])
        self.link(self.inputs.outputs["Cycles"], mix1.inputs[1])
        self.link(self.inputs.outputs["Eevee"], mix2.inputs[1])
        self.link(trans.outputs[0], mix1.inputs[2])
        self.link(trans.outputs[0], mix2.inputs[2])
        self.link(mix1.outputs[0], self.outputs.inputs["Cycles"])
        self.link(mix1.outputs[0], self.outputs.inputs["Eevee"])

# ---------------------------------------------------------------------
#   Diffuse Group
# ---------------------------------------------------------------------


class DiffuseShaderGroup(MixShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 3)
        self.input("NodeSocketColor", "Color")
        self.input("NodeSocketFloat", "Roughness")
        self.input("NodeSocketVector", "Normal")

    def addNodes(self, args=None):
        super().addNodes(args)

        diffuse = self.add_node("ShaderNodeBsdfDiffuse", 1)

        self.link(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.link(
            self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.link(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.link(diffuse.outputs[0], self.mix1.inputs[2])
        self.link(diffuse.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Glossy Group
# ---------------------------------------------------------------------


class GlossyShaderGroup(MixShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 3)
        self.input("NodeSocketColor", "Color")
        self.input("NodeSocketFloat", "Roughness")
        self.input("NodeSocketVector", "Normal")

    def addNodes(self, args=None):
        super().addNodes(args)

        glossy = self.add_node("ShaderNodeBsdfGlossy", 1)

        self.link(self.inputs.outputs["Color"], glossy.inputs["Color"])
        self.link(
            self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.link(self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        self.link(glossy.outputs[0], self.mix1.inputs[2])
        self.link(glossy.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Top Coat Group
# ---------------------------------------------------------------------


class TopCoatShaderGroup(MixShaderGroup):

    def __init__(self):
        super().__init__()
        self.mat_group.insockets += ["Color", "Roughness",
                                     "Bump", "Height", "Distance", "Normal"]

    def create(self, node, name, parent):
        super().create(node, name, parent, 4)

        self.input("NodeSocketColor", "Color")
        self.input("NodeSocketFloat", "Roughness")
        self.input("NodeSocketFloat", "Bump")
        self.input("NodeSocketFloat", "Distance")
        self.input("NodeSocketFloat", "Height")
        self.input("NodeSocketVector", "Normal")

    def addNodes(self, args=None):
        super().addNodes(args)

        bump = self.add_node("ShaderNodeBump", 1)

        self.link(self.inputs.outputs["Bump"], bump.inputs["Strength"])
        self.link(self.inputs.outputs["Height"], bump.inputs["Height"])
        self.link(
            self.inputs.outputs["Distance"], bump.inputs["Distance"])
        self.link(self.inputs.outputs["Normal"], bump.inputs["Normal"])

        glossy = self.add_node("ShaderNodeBsdfGlossy", 2)
        self.link(self.inputs.outputs["Color"], glossy.inputs["Color"])
        self.link(
            self.inputs.outputs["Roughness"], glossy.inputs["Roughness"])
        self.link(bump.outputs["Normal"], glossy.inputs["Normal"])
        self.link(glossy.outputs[0], self.mix1.inputs[2])
        self.link(glossy.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Refraction Group
# ---------------------------------------------------------------------


class RefractionShaderGroup(MixShaderGroup):

    def __init__(self):
        super().__init__()
        self.mat_group.insockets += [
            "Thin Wall",
            "Refraction Color", "Refraction Roughness", "Refraction IOR",
            "Glossy Color", "Glossy Roughness", "Fresnel IOR", "Normal"]

    def create(self, node, name, parent):
        super().create(node, name, parent, 5)

        self.input("NodeSocketFloat", "Thin Wall")
        self.input("NodeSocketColor", "Refraction Color")
        self.input("NodeSocketFloat", "Refraction Roughness")
        self.input("NodeSocketFloat", "Refraction IOR")
        self.input("NodeSocketFloat", "Fresnel IOR")
        self.input("NodeSocketColor", "Glossy Color")
        self.input("NodeSocketFloat", "Glossy Roughness")
        self.input("NodeSocketVector", "Normal")

    def addNodes(self, args=None):
        super().addNodes(args)

        refr = self.add_node("ShaderNodeBsdfRefraction", 1)
        self.link(
            self.inputs.outputs["Refraction Color"], refr.inputs["Color"])
        self.link(
            self.inputs.outputs["Refraction Roughness"], refr.inputs["Roughness"])
        self.link(
            self.inputs.outputs["Refraction IOR"], refr.inputs["IOR"])
        self.link(self.inputs.outputs["Normal"], refr.inputs["Normal"])

        trans = self.add_node("ShaderNodeBsdfTransparent", 1)
        self.link(
            self.inputs.outputs["Refraction Color"], trans.inputs["Color"])

        thin = self.add_node("ShaderNodeMixShader", 2)
        thin.label = "Thin Wall"
        self.link(self.inputs.outputs["Thin Wall"], thin.inputs["Fac"])
        self.link(refr.outputs[0], thin.inputs[1])
        self.link(trans.outputs[0], thin.inputs[2])

        fresnel = self.add_group(FresnelShaderGroup, "DAZ Fresnel", 2)
        self.link(
            self.inputs.outputs["Fresnel IOR"], fresnel.inputs["IOR"])
        self.link(
            self.inputs.outputs["Glossy Roughness"], fresnel.inputs["Roughness"])
        self.link(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        glossy = self.add_node("ShaderNodeBsdfGlossy", 2)
        self.link(
            self.inputs.outputs["Glossy Color"], glossy.inputs["Color"])
        self.link(
            self.inputs.outputs["Glossy Roughness"], glossy.inputs["Roughness"])
        self.link(self.inputs.outputs["Normal"], glossy.inputs["Normal"])

        mix = self.add_node("ShaderNodeMixShader", 3)

        self.link(fresnel.outputs[0], mix.inputs[0])
        self.link(thin.outputs[0], mix.inputs[1])
        self.link(glossy.outputs[0], mix.inputs[2])

        self.link(mix.outputs[0], self.mix1.inputs[2])
        self.link(mix.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Fake Caustics Group
# ---------------------------------------------------------------------


class FakeCausticsShaderGroup(MixShaderGroup):

    def create(self, node, name, parent):
        super().create(node, name, parent, 6)

    def addNodes(self, args):
        super().addNodes(args)

        normal = self.add_node("ShaderNodeNewGeometry", 1)
        incoming = self.add_node("ShaderNodeNewGeometry", 1)

        dot = self.add_node("ShaderNodeVectorMath", 2)
        dot.operation = 'DOT_PRODUCT'
        self.link(normal.outputs["Normal"], dot.inputs[0])
        self.link(incoming.outputs["Incoming"], dot.inputs[1])

        ramp = self.add_node('ShaderNodeValToRGB', 3)
        self.link(dot.outputs["Value"], ramp.inputs['Fac'])
        colramp = ramp.color_ramp
        colramp.interpolation = 'LINEAR'
        color = args[0]
        elt = colramp.elements[0]
        elt.position = 0.9
        elt.color[0:3] = 0.5*color
        elt = colramp.elements[1]
        elt.position = 1.0
        elt.color[0:3] = 10*color

        lightpath = self.add_node("ShaderNodeLightPath", 4, size=100)
        trans = self.add_node("ShaderNodeBsdfTransparent", 4)

        self.link(ramp.outputs["Color"], trans.inputs["Color"])
        self.link(lightpath.outputs["Is Shadow Ray"], self.mix1.inputs[0])
        self.link(lightpath.outputs["Is Shadow Ray"], self.mix2.inputs[0])
        self.link(trans.outputs[0], self.mix1.inputs[2])
        self.link(trans.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Transparent Group
# ---------------------------------------------------------------------


class TransparentShaderGroup(MixShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 3)
        self.input("NodeSocketColor", "Color")

    def addNodes(self, args=None):
        super().addNodes(args)
        trans = self.add_node("ShaderNodeBsdfTransparent", 1)
        self.link(self.inputs.outputs["Color"], trans.inputs["Color"])
        # Flip
        self.link(self.inputs.outputs["Cycles"], self.mix1.inputs[2])
        self.link(self.inputs.outputs["Eevee"], self.mix2.inputs[2])
        self.link(trans.outputs[0], self.mix1.inputs[1])
        self.link(trans.outputs[0], self.mix2.inputs[1])

# ---------------------------------------------------------------------
#   Translucent Group
# ---------------------------------------------------------------------


class TranslucentShaderGroup(MixShaderGroup):

    def __init__(self):
        super().__init__()
        self.mat_group.insockets += [
            "Color", "Gamma", "Scale", "Radius",
            "Cycles Mix Factor", "Eevee Mix Factor", "Normal"]

    def create(self, node, name, parent):
        super().create(node, name, parent, 4)
        self.input("NodeSocketColor", "Color")
        self.input("NodeSocketFloat", "Gamma")
        self.input("NodeSocketFloat", "Scale")
        self.input("NodeSocketVector", "Radius")
        self.input("NodeSocketFloat", "Cycles Mix Factor")
        self.input("NodeSocketFloat", "Eevee Mix Factor")
        self.input("NodeSocketVector", "Normal")

    def addNodes(self, args=None):
        super().addNodes(args)

        trans = self.add_node("ShaderNodeBsdfTranslucent", 1)
        self.link(self.inputs.outputs["Color"], trans.inputs["Color"])
        self.link(self.inputs.outputs["Normal"], trans.inputs["Normal"])

        gamma = self.add_node("ShaderNodeGamma", 1)
        self.link(self.inputs.outputs["Color"], gamma.inputs["Color"])
        self.link(self.inputs.outputs["Gamma"], gamma.inputs["Gamma"])

        sss = self.add_node("ShaderNodeSubsurfaceScattering", 1)
        sss.falloff = Settings.sssMethod

        self.link(gamma.outputs["Color"], sss.inputs["Color"])
        self.link(self.inputs.outputs["Scale"], sss.inputs["Scale"])
        self.link(self.inputs.outputs["Radius"], sss.inputs["Radius"])
        self.link(self.inputs.outputs["Normal"], sss.inputs["Normal"])

        cmix = self.add_node("ShaderNodeMixShader", 2)
        self.link(
            self.inputs.outputs["Cycles Mix Factor"], cmix.inputs[0])
        self.link(trans.outputs[0], cmix.inputs[1])
        self.link(sss.outputs[0], cmix.inputs[2])

        emix = self.add_node("ShaderNodeMixShader", 2)
        self.link(self.inputs.outputs["Eevee Mix Factor"], emix.inputs[0])
        self.link(trans.outputs[0], emix.inputs[1])
        self.link(sss.outputs[0], emix.inputs[2])

        self.link(cmix.outputs[0], self.mix1.inputs[2])
        self.link(emix.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Makeup Group
# ---------------------------------------------------------------------


class MakeupShaderGroup(MixShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 3)

        self.input("NodeSocketColor", "Color")
        self.input("NodeSocketFloat", "Roughness")
        self.input("NodeSocketVector", "Normal")

    def addNodes(self, args=None):
        super().addNodes(args)

        diffuse = self.add_node("ShaderNodeBsdfDiffuse", 1)
        self.link(self.inputs.outputs["Color"], diffuse.inputs["Color"])
        self.link(
            self.inputs.outputs["Roughness"], diffuse.inputs["Roughness"])
        self.link(self.inputs.outputs["Normal"], diffuse.inputs["Normal"])
        self.link(diffuse.outputs[0], self.mix1.inputs[2])
        self.link(diffuse.outputs[0], self.mix2.inputs[2])

# ---------------------------------------------------------------------
#   Ray Clip Group
# ---------------------------------------------------------------------


class RayClipShaderGroup(ShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 4)
        self.input("NodeSocketShader", "Shader")
        self.input("NodeSocketColor", "Color")
        self.output("NodeSocketShader", "Shader")

    def addNodes(self, args=None):
        lpath = self.add_node("ShaderNodeLightPath", 1)

        max = self.add_node("ShaderNodeMath", 2)
        max.operation = 'MAXIMUM'
        self.link(lpath.outputs["Is Shadow Ray"], max.inputs[0])
        self.link(lpath.outputs["Is Reflection Ray"], max.inputs[1])

        trans = self.add_node("ShaderNodeBsdfTransparent", 2)
        self.link(self.inputs.outputs["Color"], trans.inputs["Color"])

        mix = self.add_node("ShaderNodeMixShader", 3)
        self.link(max.outputs[0], mix.inputs[0])
        self.link(self.inputs.outputs["Shader"], mix.inputs[1])
        self.link(trans.outputs[0], mix.inputs[2])

        self.link(mix.outputs[0], self.outputs.inputs["Shader"])

# ---------------------------------------------------------------------
#   Dual Lobe Group
# ---------------------------------------------------------------------


class DualLobeShaderGroup(ShaderGroup):

    def __init__(self):
        super().__init__()
        self.mat_group.insockets += [
            "Fac", "Cycles", "Eevee", "Weight", "IOR",
            "Roughness 1", "Roughness 2"]

    def create(self, node, name, parent):
        super().create(node, name, parent, 4)
        self.input("NodeSocketFloat", "Fac")
        self.input("NodeSocketShader", "Cycles")
        self.input("NodeSocketShader", "Eevee")
        self.input("NodeSocketFloat", "Weight")
        self.input("NodeSocketFloat", "IOR")
        self.input("NodeSocketFloat", "Roughness 1")
        self.input("NodeSocketFloat", "Roughness 2")
        self.input("NodeSocketVector", "Normal")
        self.output("NodeSocketShader", "Cycles")
        self.output("NodeSocketShader", "Eevee")

    def addNodes(self, args=None):
        fresnel1 = self.addFresnel(True, "Roughness 1")
        glossy1 = self.addGlossy("Roughness 1", self.lobe1Normal)
        cycles1 = self.mixGlossy(fresnel1, glossy1, "Cycles")
        eevee1 = self.mixGlossy(fresnel1, glossy1, "Eevee")
        fresnel2 = self.addFresnel(False, "Roughness 2")
        glossy2 = self.addGlossy("Roughness 2", self.lobe2Normal)
        cycles2 = self.mixGlossy(fresnel2, glossy2, "Cycles")
        eevee2 = self.mixGlossy(fresnel2, glossy2, "Eevee")
        self.mixOutput(cycles1, cycles2, "Cycles")
        self.mixOutput(eevee1, eevee2, "Eevee")

    def addGlossy(self, roughness, useNormal):
        glossy = self.add_node("ShaderNodeBsdfGlossy", 1)
        self.link(self.inputs.outputs["Weight"], glossy.inputs["Color"])
        self.link(
            self.inputs.outputs[roughness], glossy.inputs["Roughness"])
        if useNormal:
            self.link(
                self.inputs.outputs["Normal"], glossy.inputs["Normal"])
        return glossy

    def mixGlossy(self, fresnel, glossy, slot):
        mix = self.add_node("ShaderNodeMixShader", 2)
        self.link(fresnel.outputs[0], mix.inputs[0])
        self.link(self.inputs.outputs[slot], mix.inputs[1])
        self.link(glossy.outputs[0], mix.inputs[2])
        return mix

    def mixOutput(self, node1, node2, slot):
        mix = self.add_node("ShaderNodeMixShader", 3)
        self.link(self.inputs.outputs["Fac"], mix.inputs[0])
        self.link(node1.outputs[0], mix.inputs[2])
        self.link(node2.outputs[0], mix.inputs[1])
        self.link(mix.outputs[0], self.outputs.inputs[slot])


class DualLobeUberIrayShaderGroup(DualLobeShaderGroup):
    lobe1Normal = True
    lobe2Normal = False

    def addFresnel(self, useNormal, roughness):
        fresnel = self.add_group(UberFresnelShaderGroup, "DAZ Fresnel Uber", 1)
        self.link(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.link(
            self.inputs.outputs[roughness], fresnel.inputs["Roughness"])
        if useNormal:
            self.link(
                self.inputs.outputs["Normal"], fresnel.inputs["Normal"])
        return fresnel


class DualLobePBRSkinShaderGroup(DualLobeShaderGroup):
    lobe1Normal = True
    lobe2Normal = True

    def addFresnel(self, useNormal, roughness):
        fresnel = self.add_group(
            PBRSkinFresnelShaderGroup, "DAZ Fresnel PBR", 1)
        self.link(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.link(
            self.inputs.outputs[roughness], fresnel.inputs["Roughness"])
        self.link(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])
        return fresnel

# ---------------------------------------------------------------------
#   Volume Group
# ---------------------------------------------------------------------


class VolumeShaderGroup(ShaderGroup):

    def __init__(self):
        super().__init__()
        self.mat_group.insockets += [
            "Absorbtion Color", "Absorbtion Density", "Scatter Color",
            "Scatter Density", "Scatter Anisotropy"]

    def create(self, node, name, parent):
        super().create(node, name, parent, 3)
        self.input("NodeSocketColor", "Absorbtion Color")
        self.input("NodeSocketFloat", "Absorbtion Density")
        self.input("NodeSocketColor", "Scatter Color")
        self.input("NodeSocketFloat", "Scatter Density")
        self.input("NodeSocketFloat", "Scatter Anisotropy")
        self.output("NodeSocketShader", "Volume")

    def addNodes(self, _=None):
        absorb = self.add_node("ShaderNodeVolumeAbsorption", 1)
        self.link(
            self.inputs.outputs["Absorbtion Color"], absorb.inputs["Color"])
        self.link(
            self.inputs.outputs["Absorbtion Density"], absorb.inputs["Density"])

        scatter = self.add_node("ShaderNodeVolumeScatter", 1)
        self.link(
            self.inputs.outputs["Scatter Color"], scatter.inputs["Color"])
        self.link(
            self.inputs.outputs["Scatter Density"], scatter.inputs["Density"])
        self.link(
            self.inputs.outputs["Scatter Anisotropy"], scatter.inputs["Anisotropy"])

        volume = self.add_node("ShaderNodeAddShader", 2)
        self.link(absorb.outputs[0], volume.inputs[0])
        self.link(scatter.outputs[0], volume.inputs[1])
        self.link(volume.outputs[0], self.outputs.inputs["Volume"])

# ---------------------------------------------------------------------
#   Normal Group
#
#   https://blenderartists.org/t/way-faster-normal-map-node-for-realtime-animation-playback-with-tangent-space-normals/1175379
# ---------------------------------------------------------------------


class NormalShaderGroup(ShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 8)

        strength = self.input("NodeSocketFloat", "Strength")
        strength.default_value = 1.0
        strength.min_value = 0.0
        strength.max_value = 1.0

        color = self.input("NodeSocketColor", "Color")
        color.default_value = ((0.5, 0.5, 1.0, 1.0))

        self.output("NodeSocketVector", "Normal")

    def addNodes(self, args):
        # Generate TBN from Bump Node
        frame = self.shader_graph.nodes.new("NodeFrame")
        frame.label = "Generate TBN from Bump Node"

        uvmap = self.add_node("ShaderNodeUVMap", 1, parent=frame)
        if args[0]:
            uvmap.uv_map = args[0]

        uvgrads = self.add_node("ShaderNodeSeparateXYZ",
                                2, label="UV Gradients", parent=frame)
        self.link(uvmap.outputs["UV"], uvgrads.inputs[0])

        tangent = self.add_node("ShaderNodeBump", 3,
                                label="Tangent", parent=frame)
        tangent.invert = True
        tangent.inputs["Distance"].default_value = 1
        self.link(uvgrads.outputs[0], tangent.inputs["Height"])

        bitangent = self.add_node(
            "ShaderNodeBump", 3, label="Bi-Tangent", parent=frame)
        bitangent.invert = True
        bitangent.inputs["Distance"].default_value = 1000
        self.link(uvgrads.outputs[1], bitangent.inputs["Height"])

        geo = self.add_node("ShaderNodeNewGeometry", 3,
                            label="Normal", parent=frame)

        # Transpose Matrix
        frame = self.shader_graph.nodes.new("NodeFrame")
        frame.label = "Transpose Matrix"

        sep1 = self.add_node("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.link(tangent.outputs["Normal"], sep1.inputs[0])

        sep2 = self.add_node("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.link(bitangent.outputs["Normal"], sep2.inputs[0])

        sep3 = self.add_node("ShaderNodeSeparateXYZ", 4, parent=frame)
        self.link(geo.outputs["Normal"], sep3.inputs[0])

        comb1 = self.add_node("ShaderNodeCombineXYZ", 5, parent=frame)
        self.link(sep1.outputs[0], comb1.inputs[0])
        self.link(sep2.outputs[0], comb1.inputs[1])
        self.link(sep3.outputs[0], comb1.inputs[2])

        comb2 = self.add_node("ShaderNodeCombineXYZ", 5, parent=frame)
        self.link(sep1.outputs[1], comb2.inputs[0])
        self.link(sep2.outputs[1], comb2.inputs[1])
        self.link(sep3.outputs[1], comb2.inputs[2])

        comb3 = self.add_node("ShaderNodeCombineXYZ", 5, parent=frame)
        self.link(sep1.outputs[2], comb3.inputs[0])
        self.link(sep2.outputs[2], comb3.inputs[1])
        self.link(sep3.outputs[2], comb3.inputs[2])

        # Normal Map Processing
        frame = self.shader_graph.nodes.new("NodeFrame")
        frame.label = "Normal Map Processing"

        rgb = self.add_node("ShaderNodeMixRGB", 3, parent=frame)
        self.link(self.inputs.outputs["Strength"], rgb.inputs[0])
        rgb.inputs[1].default_value = (0.5, 0.5, 1.0, 1.0)
        self.link(self.inputs.outputs["Color"], rgb.inputs[2])

        sub = self.add_node("ShaderNodeVectorMath", 4, parent=frame)
        sub.operation = 'SUBTRACT'
        self.link(rgb.outputs["Color"], sub.inputs[0])
        sub.inputs[1].default_value = (0.5, 0.5, 0.5)

        add = self.add_node("ShaderNodeVectorMath", 5, parent=frame)
        add.operation = 'ADD'
        self.link(sub.outputs[0], add.inputs[0])
        self.link(sub.outputs[0], add.inputs[1])

        # Matrix * Normal Map
        frame = self.shader_graph.nodes.new("NodeFrame")
        frame.label = "Matrix * Normal Map"

        dot1 = self.add_node("ShaderNodeVectorMath", 6, parent=frame)
        dot1.operation = 'DOT_PRODUCT'
        self.link(comb1.outputs[0], dot1.inputs[0])
        self.link(add.outputs[0], dot1.inputs[1])

        dot2 = self.add_node("ShaderNodeVectorMath", 6, parent=frame)
        dot2.operation = 'DOT_PRODUCT'
        self.link(comb2.outputs[0], dot2.inputs[0])
        self.link(add.outputs[0], dot2.inputs[1])

        dot3 = self.add_node("ShaderNodeVectorMath", 6, parent=frame)
        dot3.operation = 'DOT_PRODUCT'
        self.link(comb3.outputs[0], dot3.inputs[0])
        self.link(add.outputs[0], dot3.inputs[1])

        comb = self.add_node("ShaderNodeCombineXYZ", 7, parent=frame)
        self.link(dot1.outputs["Value"], comb.inputs[0])
        self.link(dot2.outputs["Value"], comb.inputs[1])
        self.link(dot3.outputs["Value"], comb.inputs[2])

        self.link(comb.outputs[0], self.outputs.inputs["Normal"])

# ---------------------------------------------------------------------
#   Detail Group
# ---------------------------------------------------------------------


class DetailShaderGroup(ShaderGroup):

    def __init__(self):
        super().__init__()
        self.mat_group.insockets += ["Texture",
                                     "Strength", "Max", "Min", "Normal"]


# ---------------------------------------------------------------------
#   Displacement Group
# ---------------------------------------------------------------------

class DisplacementShaderGroup(ShaderGroup):

    def __init__(self):
        super().__init__()
        self.mat_group.insockets += ["Texture",
                                     "Strength", "Max", "Min", "Normal"]

    def create(self, node, name, parent):
        super().create(node, name, parent, 4)
        self.input("NodeSocketFloat", "Texture")
        self.input("NodeSocketFloat", "Strength")
        self.input("NodeSocketFloat", "Max")
        self.input("NodeSocketFloat", "Min")
        self.input("NodeSocketVector", "Normal")
        self.output("NodeSocketVector", "Displacement")

    def addNodes(self, args=None):
        bw = self.add_node("ShaderNodeRGBToBW", 1)
        self.link(self.inputs.outputs["Texture"], bw.inputs[0])

        sub = self.add_node("ShaderNodeMath", 1)
        sub.operation = 'SUBTRACT'
        self.link(self.inputs.outputs["Max"], sub.inputs[0])
        self.link(self.inputs.outputs["Min"], sub.inputs[1])

        mult = self.add_node("ShaderNodeMath", 2)
        mult.operation = 'MULTIPLY'
        self.link(bw.outputs[0], mult.inputs[0])
        self.link(sub.outputs[0], mult.inputs[1])

        add = self.add_node("ShaderNodeMath", 2)
        add.operation = 'ADD'
        self.link(mult.outputs[0], add.inputs[0])
        self.link(self.inputs.outputs["Min"], add.inputs[1])

        disp = self.add_node("ShaderNodeDisplacement", 3)
        self.link(add.outputs[0], disp.inputs["Height"])
        disp.inputs["Midlevel"].default_value = 0
        self.link(self.inputs.outputs["Strength"], disp.inputs["Scale"])
        self.link(self.inputs.outputs["Normal"], disp.inputs["Normal"])

        self.link(disp.outputs[0], self.outputs.inputs["Displacement"])

# ---------------------------------------------------------------------
#   Decal Group
# ---------------------------------------------------------------------


class DecalShaderGroup(ShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 5)
        self.input("NodeSocketColor", "Color")
        self.input("NodeSocketFloat", "Influence")
        self.output("NodeSocketColor", "Color")
        self.output("NodeSocketFloat", "Alpha")
        self.output("NodeSocketColor", "Combined")

    def addNodes(self, args):
        empty, img = args

        texco = self.add_node("ShaderNodeTexCoord", 0)
        texco.object = empty

        mapping = self.add_node("ShaderNodeMapping", 1)
        mapping.vector_type = 'POINT'
        mapping.inputs["Location"].default_value = (0.5, 0.5, 0)
        self.link(texco.outputs["Object"], mapping.inputs["Vector"])

        tex = self.add_node("ShaderNodeTexImage", 2)
        tex.image = img
        tex.interpolation = Settings.imageInterpolation
        tex.extension = 'CLIP'
        self.link(mapping.outputs["Vector"], tex.inputs["Vector"])

        mult = self.add_node("ShaderNodeMath", 3)
        mult.operation = 'MULTIPLY'
        self.link(self.inputs.outputs["Influence"], mult.inputs[0])
        self.link(tex.outputs["Alpha"], mult.inputs[1])

        mix = self.add_node("ShaderNodeMixRGB", 4)
        mix.blend_type = 'MULTIPLY'
        self.link(mult.outputs[0], mix.inputs[0])
        self.link(self.inputs.outputs["Color"], mix.inputs[1])
        self.link(tex.outputs["Color"], mix.inputs[2])

        self.link(tex.outputs["Color"], self.outputs.inputs["Color"])
        self.link(mult.outputs[0], self.outputs.inputs["Alpha"])
        self.link(mix.outputs[0], self.outputs.inputs["Combined"])

# ---------------------------------------------------------------------
#   LIE Group
# ---------------------------------------------------------------------


class LieShaderGroup(ShaderGroup):

    def __init__(self):
        super().__init__()

    def create(self, node, name, parent):
        super().create(node, name, parent, 6)

        self.input("NodeSocketVector", "Vector")
        self.texco = self.inputs.outputs[0]
        self.input("NodeSocketFloat", "Alpha")
        self.output("NodeSocketColor", "Color")

    def addTextureNodes(self, assets, maps, colorSpace):
        texnodes = []

        for idx, asset in enumerate(assets):
            texnode, isnew = self.addSingleTexture(
                3, asset, maps[idx], colorSpace)
            if isnew:
                innode = texnode
                mapping = self.mapTexture(asset, maps[idx])
                if mapping:
                    texnode.extension = 'CLIP'
                    self.link(
                        mapping.outputs["Vector"], texnode.inputs["Vector"])
                    innode = mapping
                else:
                    img = asset.images[colorSpace]
                    if img:
                        self.setTexNode(img.name, texnode, colorSpace)
                    else:
                        msg = ("Missing image: %s" % asset.getName())
                        ErrorsStatic.report(msg, trigger=(3, 5))
                self.link(
                    self.inputs.outputs["Vector"], innode.inputs["Vector"])
            texnodes.append([texnode])

        if not texnodes:
            return

        assets_len = len(assets)

        for idx in range(1, assets_len):
            map = maps[idx]
            if map.invert:
                inv = self.add_node("ShaderNodeInvert", 4)
                node = texnodes[idx][0]
                self.link(node.outputs[0], inv.inputs["Color"])
                texnodes[idx].append(inv)

        texnode = texnodes[0][-1]
        alphamix = self.add_node("ShaderNodeMixRGB", 6)
        alphamix.blend_type = 'MIX'
        alphamix.inputs[0].default_value = 1.0

        self.link(self.inputs.outputs["Alpha"], alphamix.inputs[0])
        self.link(texnode.outputs["Color"], alphamix.inputs[1])

        masked = False

        for idx in range(1, assets_len):
            map = maps[idx]
            if map.ismask:
                if idx == assets_len-1:
                    continue
                # ShaderNodeMixRGB
                mix = self.add_node("ShaderNodeMixRGB", 5)
                mix.blend_type = 'MULTIPLY'
                mix.use_alpha = False
                mask = texnodes[idx][-1]
                self.setColorSpace(mask, 'NONE')
                self.link(mask.outputs["Color"], mix.inputs[0])
                self.link(texnode.outputs["Color"], mix.inputs[1])
                self.link(
                    texnodes[idx+1][-1].outputs["Color"], mix.inputs[2])
                texnode = mix
                masked = True
            elif not masked:
                mix = self.add_node("ShaderNodeMixRGB", 5)
                alpha = setMixOperation(mix, map)
                mix.inputs[0].default_value = alpha
                node = texnodes[idx][-1]
                base = texnodes[idx][0]
                if alpha != 1:
                    node = self.multiplyScalarTex(alpha, base, "Alpha", 4)
                    self.link(node.outputs[0], mix.inputs[0])
                elif "Alpha" in base.outputs.keys():
                    self.link(base.outputs["Alpha"], mix.inputs[0])
                else:
                    print("No LIE alpha:", base)
                    mix.inputs[0].default_value = alpha
                mix.use_alpha = True
                self.link(texnode.outputs["Color"], mix.inputs[1])
                self.link(
                    texnodes[idx][-1].outputs["Color"], mix.inputs[2])
                texnode = mix
                masked = False
            else:
                masked = False

        self.link(texnode.outputs[0], alphamix.inputs[2])
        self.link(alphamix.outputs[0], self.outputs.inputs["Color"])

    def mapTexture(self, asset, map_):
        if not asset.hasMapping(map_):
            return
        data = asset.getMapping(self.material, map_)
        return self.addMappingNode(data, map_)


def setMixOperation(mix, map_):
    # alpha = 1
    op = map_.operation

    if op == "multiply":
        mix.blend_type = 'MULTIPLY'
        # useAlpha = True
    elif op == "add":
        mix.blend_type = 'ADD'
        # useAlpha = False
    elif op == "subtract":
        mix.blend_type = 'SUBTRACT'
        # useAlpha = False
    elif op == "alpha_blend":
        mix.blend_type = 'MIX'
        # useAlpha = True
    else:
        print("MIX", 'asset', map_.operation)
        # print("MIX", asset, map.operation)

    return map_.transparency

# ----------------------------------------------------------
#   Make shader group
# ----------------------------------------------------------


@Registrar()
class DAZ_OT_MakeShaderGroups(DazPropsOperator):
    bl_idname = "daz.make_shader_groups"
    bl_label = "Make Shader Groups"
    bl_description = "Create shader groups for the active material"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    groups = {
        "useFresnel": (FresnelShaderGroup, "DAZ Fresnel", []),
        "useEmission": (EmissionShaderGroup, "DAZ Emission", []),
        "useOneSided": (OneSidedShaderGroup, "DAZ VectorStatic.one-Sided", []),
        "useOverlay": (DiffuseShaderGroup, "DAZ Overlay", []),
        "useGlossy": (GlossyShaderGroup, "DAZ Glossy", []),
        "useTopCoat": (TopCoatShaderGroup, "DAZ Top Coat", []),
        "useRefraction": (RefractionShaderGroup, "DAZ Refraction", []),
        "useFakeCaustics": (FakeCausticsShaderGroup, "DAZ Fake Caustics", [ColorStatic.WHITE]),
        "useTransparent": (TransparentShaderGroup, "DAZ Transparent", []),
        "useTranslucent": (TranslucentShaderGroup, "DAZ Translucent", []),
        "useRayClip": (RayClipShaderGroup, "DAZ Ray Clip", []),
        "useDualLobeUber": (DualLobeUberIrayShaderGroup, "DAZ Dual Lobe Uber", []),
        "useDualLobePBR": (DualLobePBRSkinShaderGroup, "DAZ Dual Lobe PBR", []),
        "useVolume": (VolumeShaderGroup, "DAZ Volume", []),
        "useNormal": (NormalShaderGroup, "DAZ Normal", ["uvname"]),
        "useDisplacement": (DisplacementShaderGroup, "DAZ Displacement", []),
        "useDecal": (DecalShaderGroup, "DAZ Decal", [None, None]),
    }

    useFresnel: BoolProperty(name="Fresnel", default=False)
    useEmission: BoolProperty(name="Emission", default=False)
    useOneSided: BoolProperty(name="VectorStatic.one Sided", default=False)
    useOverlay: BoolProperty(name="Diffuse Overlay", default=False)
    useGlossy: BoolProperty(name="Glossy", default=False)
    useTopCoat: BoolProperty(name="Top Coat", default=False)
    useRefraction: BoolProperty(name="Refraction", default=False)
    useFakeCaustics: BoolProperty(name="Fake Caustics", default=False)
    useTransparent: BoolProperty(name="Transparent", default=False)
    useTranslucent: BoolProperty(name="Translucent", default=False)
    useSSS: BoolProperty(name="Subsurface Scattering", default=False)
    useRayClip: BoolProperty(name="Ray Clip", default=False)
    useDualLobeUber: BoolProperty(
        name="Dual Lobe (Uber Shader)", default=False)
    useDualLobePBR: BoolProperty(name="Dual Lobe (PBR Skin)", default=False)
    useVolume: BoolProperty(name="Volume", default=False)
    useNormal: BoolProperty(name="Normal", default=False)
    useDisplacement: BoolProperty(name="Displacement", default=False)
    useDecal: BoolProperty(name="Decal", default=False)

    def draw(self, context):
        for key in self.groups.keys():
            self.layout.prop(self, key)

    def run(self, context):
        from daz_import.Elements.Material.Cycles import CyclesMaterial, CyclesShader

        ob = context.object
        mat = ob.data.materials[ob.active_material_index]

        if mat is None:
            raise DazError("No active material")

        cmat = CyclesMaterial("")

        shader = CyclesShader(cmat)
        shader.set_material(mat)
        shader.column = 0

        for key, value in self.groups.items():
            if not getattr(self, key):
                continue

            group, gname, args = value

            shader.column += 1
            _ = shader.add_group(group, gname, args=args)
