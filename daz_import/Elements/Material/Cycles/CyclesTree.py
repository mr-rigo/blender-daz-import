from __future__ import annotations
import os
from typing import Type, Dict, List, Tuple
from mathutils import Vector

import bpy

from bpy.types import Material as BlenderMaterial
from bpy.types import ShaderNode, NodeLink, \
    ShaderNodeTexImage, ShaderNodeBump, NodeSocketVector,\
    ShaderNodeGroup, ShaderNodeTexImage, ShaderNodeMapping


from daz_import.Elements.Color import ColorStatic
from daz_import.Lib.Errors import DazError
from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Lib.Utility import UtilityStatic
from daz_import.Lib.Settings import Settings
from daz_import.Elements.Material.Cycles.CyclesStatic import CyclesStatic
from daz_import.Elements.Material.Material import Material
from daz_import.Elements.ShaderGraph import ShaderGraph, EmissionShader, DiffuseShader


class CyclesShader(CyclesStatic):
    type = 'CYCLES'

    def __init__(self, material: Material):
        self.material: Material = material
        self.easy_shader = False

        self.ycoords = self.NCOLUMNS * [2 * self.YSIZE]
        self.cycles: ShaderNodeGroup = None
        self.eevee: ShaderNodeGroup = None
        self.column = 4

        self.texnodes: Dict[str, BlenderMaterial] = {}

        self.nodes: List[ShaderNode] = []
        self.links: List[NodeLink] = None

        self.group = None
        self.groups = {}
        self.liegroups = []

        self.diffuseTex: ShaderNodeTexImage = None
        self.fresnel = None
        self.normal = None

        self.bump: ShaderNodeBump = None
        self.bumpval = 0
        self.bumptex: ShaderNodeTexImage = None

        self.texco: NodeSocketVector = None

        self.texcos: Dict[str, NodeSocketVector] = {}

        self.displacement = None
        self.volume: ShaderNodeGroup = None
        self.useCutout = False
        self.useTranslucency = False

    def __repr__(self):
        return ("<Cycles %s %s %s>" % (self.material.rna, self.nodes, self.links))

    def getValue(self, channel, default):
        return self.material.channelsData.getValue(channel, default)

    def isEnabled(self, key) -> bool:
        return self.material.enabled.get(key)

    def getColor(self, channel, default):
        return self.material.getColor(channel, default)

    def addNode(self, stype, col=None, size=0, label=None, parent=None) -> ShaderNode:
        if col is None:
            col = self.column

        node = self.nodes.new(type=stype)

        node.location = ((col-2)*self.XSIZE, self.ycoords[col])
        self.ycoords[col] -= (self.YSIZE + size)

        if label:
            node.label = label

        if parent:
            node.parent = parent
        return node

    def getTexco(self, uv: str) -> NodeSocketVector:
        key = self.material.getUvKey(uv, self.texcos)

        if key is None:
            return self.texco

        if key not in self.texcos.keys():
            self.addUvNode(key, key)

        return self.texcos.get(key)

    def getCyclesSocket(self):
        if out := self.cycles.outputs.get("Cycles"):
            return out
        else:
            return self.cycles.outputs[0]

    def getEeveeSocket(self):
        if out := self.eevee.outputs.get("Eevee"):
            return out
        else:
            return self.eevee.outputs[0]

    def addGroup(self, cls: Type, name, col=None,
                 size=0, args=[], force=False):
        from daz_import.Elements.ShaderGroup import ShaderGroup

        if col is None:
            col = self.column

        node = self.addNode("ShaderNodeGroup", col, size=size)
        group: ShaderGroup = cls()

        if name in bpy.data.node_groups.keys() and not force:
            tree = bpy.data.node_groups.get(name)
            if group.mat_group.checkSockets(tree):
                node.node_tree = tree
                return node

        group.create(node, name, self)
        group.addNodes(args)

        return node

    def addShellGroup(self, shell, push):
        shmat = shell.material

        shmat.isShellMat = True
        shname = shell.name

        if (shmat.getValue("getChannelCutoutOpacity", 1) == 0 or
                shmat.getValue("getChannelOpacity", 1) == 0):
            print("Invisible shell %s for %s" % (shname, self.material.name))

            return None

        nname = f"{shname}_{self.material.name}"

        node = self.addNode("ShaderNodeGroup")

        node.width = 240
        node.name = nname
        node.label = shname

        if shell.shader_object:
            node.node_tree = shell.shader_object
            node.inputs["Influence"].default_value = 1.0

            return node
        elif shell.match and shell.match.shader_object:
            node.node_tree = shell.shader_object = shell.match.shader_object
            node.inputs["Influence"].default_value = 1.0

            return node

        if self.type == 'CYCLES':
            from daz_import.Elements.ShaderGroup import OpaqueShellCyclesGroup, RefractiveShellCyclesGroup
            if shmat.refractive:
                group = RefractiveShellCyclesGroup(push)
            else:
                group = OpaqueShellCyclesGroup(push)
        elif self.type == 'PBR':
            from daz_import.Elements.ShaderGroup import OpaqueShellPbrGroup, RefractiveShellPbrGroup
            if shmat.refractive:
                group = RefractiveShellPbrGroup(push)
            else:
                group = OpaqueShellPbrGroup(push)
        else:
            raise RuntimeError("Bug Cycles type %s" % self.type)

        group.create(node, nname, self)
        group.addNodes((shmat, shell.uv))

        node.inputs["Influence"].default_value = 1.0
        shell.shader_object = shmat.shader_object = node.node_tree
        shmat.geometry = self.material.geometry

        return node

    def build(self):
        self.makeTree()
        if self.easy_shader:
            self.easy_build()
            return

        self.buildLayer()
        self.buildCutout()
        self.buildVolume()
        self.buildDisplacementNodes()
        self.buildShells()
        self.buildOutput()

    def easy_build(self):
        graph = ShaderGraph(self.material.rna)
        shader = DiffuseShader(graph)

        # shader.diffuse.default((1, 1, 1, 1))
        # shader.specular.default(0.2)

        graph.output.surface += shader.output

        _, diffuse = self.getDiffuseColor()

        if diffuse:
            shader.diffuse += diffuse.outputs['Color']

        # getGlossyColor
        # getTranslucentColor
        # getRefractionColor

    def buildShells(self):
        shells = []
        n = 0

        for shell in self.material.shells.values():
            for geonode in shell.geometry.nodes.values():
                shells.append((geonode.push, n, shell))
                n += 1

        shells.sort()

        if shells:
            self.column += 1

        for push, n, shell in shells:
            node = self.addShellGroup(shell, push)
            if not node:
                continue

            self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
            self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
            self.links.new(self.getTexco(shell.uv), node.inputs["UV"])

            if self.displacement:
                self.links.new(self.displacement,
                               node.inputs["Displacement"])

            self.cycles = self.eevee = node

            self.displacement = node.outputs["Displacement"]
            self.ycoords[self.column] -= 50

    def buildLayer(self, uvname=''):
        self.buildNormal(uvname)
        self.buildBump()
        self.buildDetail(uvname)
        self.buildDiffuse()

        self.buildTranslucency()
        self.buildMakeup()
        self.buildOverlay()

        if self.material.dualLobeWeight == 1:
            self.buildDualLobe()
        elif self.material.dualLobeWeight == 0:
            self.buildGlossy()
        else:
            self.buildGlossy()
            self.buildDualLobe()

        if self.material.refractive:
            self.buildRefraction()

        self.buildTopCoat()
        self.buildEmission()

        return self.cycles

    def makeTree(self, slot="UV"):
        mat = self.material.rna
        if not mat:
            return

        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        if self.easy_shader:
            return

        return self.addTexco(slot)

    def addTexco(self, slot):
        if self.easy_shader:
            return

        if self.material.useDefaultUvs:
            node = self.addNode("ShaderNodeTexCoord", 1)
            self.texco = node.outputs[slot]
        else:
            node = self.addNode("ShaderNodeUVMap", 1)
            node.uv_map = self.material.uv_set.name
            self.texco = node.outputs["UV"]

        ox = self.getValue("getChannelHorizontalOffset", 0)
        oy = self.getValue("getChannelVerticalOffset", 0)
        kx = self.getValue("getChannelHorizontalTiles", 1)
        ky = self.getValue("getChannelVerticalTiles", 1)

        self.mapTexco(ox, oy, kx, ky)

        for key, uvset in self.material.uv_sets.items():
            self.addUvNode(key, uvset.name)

        return node

    def addUvNode(self, key, uvname):
        node = self.addNode("ShaderNodeUVMap", 1)
        node.uv_map = uvname
        self.texcos[key] = node.outputs["UV"]

    def mapTexco(self, ox, oy, kx, ky):
        if ox != 0 or oy != 0 or kx not in [0, 1] or ky not in [0, 1]:
            sx = sy = 1
            dx = dy = 0

            if kx != 0:
                sx = 1/kx
                dx = -ox/kx

            if ky != 0:
                sy = 1/ky
                dy = oy/ky

            mapping = self.addMappingNode((dx, dy, sx, sy, 0), None)
            if not mapping:
                return

            self.linkVector(self.texco, mapping, 0)
            self.texco = mapping

    def addMappingNode(self, data, map) -> ShaderNodeMapping:
        dx, dy, sx, sy, rz = data

        if (sx != 1 or sy != 1 or dx != 0 or dy != 0 or rz != 0):
            mapping = self.addNode("ShaderNodeMapping", 1)
            mapping.vector_type = 'TEXTURE'

            if hasattr(mapping, "translation"):
                mapping.translation = (dx, dy, 0)
                mapping.scale = (sx, sy, 1)
                if rz != 0:
                    mapping.rotation = (0, 0, rz)
            else:
                mapping.inputs['Location'].default_value = (dx, dy, 0)
                mapping.inputs['Scale'].default_value = (sx, sy, 1)
                if rz != 0:
                    mapping.inputs['Rotation'].default_value = (0, 0, rz)

            if map and not map.invert and hasattr(mapping, "use_min"):
                mapping.use_min = mapping.use_max = 1

            return mapping
        return None


# -------------------------------------------------------------
#   Normal
# -------------------------------------------------------------


    def buildNormal(self, uvname):
        if not self.isEnabled("Normal"):
            return

        strength, tex = self.getColorTex("getChannelNormal", "NONE", 1.0)

        if strength > 0 and tex:
            self.buildNormalMap(strength, tex, uvname)

    def buildNormalMap(self, strength, tex, uvname):
        self.normal = self.addNode("ShaderNodeNormalMap", col=3)
        self.normal.space = "TANGENT"

        if uvname:
            self.normal.uv_map = uvname
        elif self.material.uv_set:
            self.normal.uv_map = self.material.uv_set.name

        self.normal.inputs["Strength"].default_value = strength
        self.links.new(tex.outputs[0], self.normal.inputs["Color"])

# -------------------------------------------------------------
#   Bump
# -------------------------------------------------------------

    def buildBump(self):
        if not self.isEnabled("Bump"):
            return

        self.bumpval, self.bumptex = self.getColorTex(
            "getChannelBump", "NONE", 0, False)

        if self.bumpval and self.bumptex:
            self.bump = self.buildBumpMap(self.bumpval, self.bumptex, col=3)
            self.linkNormal(self.bump)

    def buildBumpMap(self, bump, bumptex, col=3):
        node = self.addNode("ShaderNodeBump", col=col)
        node.inputs["Strength"].default_value = bump * Settings.bumpFactor
        self.links.new(bumptex.outputs[0], node.inputs["Height"])
        self.material.addGeoBump(bumptex, node.inputs["Distance"])
        return node

    def linkBumpNormal(self, node):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], node.inputs["Normal"])
        elif self.normal:
            self.links.new(
                self.normal.outputs["Normal"], node.inputs["Normal"])

    def linkBump(self, node):
        if self.bump:
            self.links.new(self.bump.outputs["Normal"], node.inputs["Normal"])

    def linkNormal(self, node):
        if self.normal:
            self.links.new(
                self.normal.outputs["Normal"], node.inputs["Normal"])

# -------------------------------------------------------------
#   Detail
# -------------------------------------------------------------

    def buildDetail(self, uvname):
        if not self.isEnabled("Detail"):
            return
        weight, wttex = self.getColorTex(["Detail Weight"], "NONE", 0.0)
        if weight == 0:
            return
        texco = self.texco
        ox = Settings.scale_*self.getValue(["Detail Horizontal Offset"], 0)
        oy = Settings.scale_*self.getValue(["Detail Vertical Offset"], 0)
        kx = self.getValue(["Detail Horizontal Tiles"], 1)
        ky = self.getValue(["Detail Vertical Tiles"], 1)
        self.mapTexco(ox, oy, kx, ky)

        strength, tex = self.getColorTex(["Detail Normal Map"], "NONE", 1.0)
        weight = weight*strength
        mode = self.getValue(["Detail Normal Map Mode"], 0)
        # Height Map, Normal Map
        if mode == 0:
            if weight == 0:
                pass
            elif self.bump:
                link = self.getLinkTo(self, self.bump, "Height")
                if link:
                    mult = self.addNode("ShaderNodeMath", 3)
                    mult.operation = 'MULTIPLY_ADD'
                    self.links.new(tex.outputs[0], mult.inputs[0])
                    self.linkScalar(wttex, mult, weight, 1)
                    self.links.new(link.from_socket, mult.inputs[2])
                    self.links.new(
                        mult.outputs["Value"], self.bump.inputs["Height"])
            else:
                tex = self.multiplyTexs(tex, wttex)
                self.bump = self.buildBumpMap(weight, tex, col=3)
                self.linkNormal(self.bump)
        elif mode == 1:
            if weight == 0:
                pass
            elif self.normal:
                link = self.getLinkTo(self, self.normal, "Color")
                if link:
                    mix = self.addNode("ShaderNodeMixRGB", 3)
                    mix.blend_type = 'OVERLAY'
                    self.linkScalar(wttex, mix, weight, "Fac")

                    NORMAL = (0.5, 0.5, 1, 1)
                    mix.inputs["Color1"].default_value = NORMAL
                    mix.inputs["Color2"].default_value = NORMAL

                    self.links.new(link.from_socket, mix.inputs["Color1"])

                    if tex:
                        self.links.new(tex.outputs[0], mix.inputs["Color2"])
                    self.links.new(
                        mix.outputs["Color"], self.normal.inputs["Color"])
                else:
                    self.links.new(tex.outputs[0], self.normal.inputs["Color"])
            else:
                self.buildNormalMap(weight, tex, uvname)
                if wttex:
                    self.links.new(
                        wttex.outputs[0], self.normal.inputs["Strength"])
                if self.bump:
                    self.links.new(
                        self.normal.outputs["Normal"], self.bump.inputs["Normal"])

        self.texco = texco

# -------------------------------------------------------------
#   Diffuse and Diffuse Overlay
# -------------------------------------------------------------

    def getDiffuseColor(self) -> Tuple[Vector, ShaderNode]:
        color, tex = self.getColorTex(
            "getChannelDiffuse", "COLOR", ColorStatic.WHITE)
        effect = self.getValue(["Base Color Effect"], 0)
        if effect > 0:  # Scatter Transmit, Scatter Transmit Intensity
            tint = self.getColor(["SSS Reflectance Tint"], ColorStatic.WHITE)
            color = self.compProd(color, tint)
        return color, tex

    def compProd(self, x, y):
        return [x[0]*y[0], x[1]*y[1], x[2]*y[2]]

    def buildDiffuse(self):
        self.column = 4
        if not self.isEnabled("Diffuse"):
            return
        color, tex = self.getDiffuseColor()
        self.diffuseTex = tex
        node = self.addNode("ShaderNodeBsdfDiffuse")
        self.cycles = self.eevee = node
        self.linkColor(tex, node, color, "Color")
        roughness, roughtex = self.getColorTex(
            ["Diffuse Roughness"], "NONE", 0, False)
        if self.isEnabled("Detail"):
            detrough, dettex = self.getColorTex(
                ["Detail Specular Roughness Mult"], "NONE", 0, False)
            roughness *= detrough
            roughtex = self.multiplyTexs(dettex, roughtex)
        self.setRoughness(node, "Roughness", roughness, roughtex)
        self.linkBumpNormal(node)
        Settings.usedFeatures_["Diffuse"] = True

    def buildOverlay(self):
        if self.getValue(["Diffuse Overlay Weight"], 0):
            self.column += 1
            slot = self.getImageSlot(["Diffuse Overlay Weight"])
            weight, wttex = self.getColorTex(
                ["Diffuse Overlay Weight"], "NONE", 0, slot=slot)
            if self.getValue(["Diffuse Overlay Weight Squared"], False):
                power = 4
            else:
                power = 2
            if wttex:
                wttex = self.raiseToPower(wttex, power, slot)
            color, tex = self.getColorTex(
                ["Diffuse Overlay Color"], "COLOR", ColorStatic.WHITE)
            from daz_import.Elements.ShaderGroup import DiffuseShaderGroup

            node = self.addGroup(DiffuseShaderGroup, "DAZ Overlay")
            self.linkColor(tex, node, color, "Color")
            roughness, roughtex = self.getColorTex(
                ["Diffuse Overlay Roughness"], "NONE", 0, False)
            self.setRoughness(node, "Roughness", roughness, roughtex)
            self.linkBumpNormal(node)
            self.mixWithActive(weight**power, wttex, node)
            return True
        else:
            return False

    def getImageSlot(self, attr):
        if self.material.getImageMod(attr, "grayscale_mode") == "alpha":
            return "Alpha"
        else:
            return 0

    def raiseToPower(self, tex, power, slot):
        node = self.addNode("ShaderNodeMath", col=self.column-1)
        node.operation = 'POWER'
        node.inputs[1].default_value = power
        if slot not in tex.outputs.keys():
            slot = 0
        self.links.new(tex.outputs[slot], node.inputs[0])
        return node

    def getColorTex(self, attr, colorSpace, default, useFactor=True, useTex=True, maxval=0, value=None, slot=0):
        channel = self.material.channelsData.getChannel(attr)
        if channel is None:
            return default, None

        if isinstance(channel, tuple):
            channel = channel[0]

        if useTex:
            tex = self.addTexImageNode(channel, colorSpace)
        else:
            tex = None

        if value is not None:
            pass
        elif channel["type"] in ["color", "float_color"]:
            value = self.material.getChannelColor(channel, default)
        else:
            value = self.material.channelsData.getChannelValue(
                channel, default)
            if value < 0:
                return 0, None

        # if useFactor:
        #     value, tex = self.multiplySomeTex(value, tex, slot)

        if VectorStatic.is_vector(value) and not VectorStatic.is_vector(default):
            value = (value[0] + value[1] + value[2])/3

        if not VectorStatic.is_vector(value) and maxval and value > maxval:
            value = maxval

        return value, tex

# -------------------------------------------------------------
#  Makeup
# -------------------------------------------------------------

    def buildMakeup(self):
        if not self.getValue(["Makeup Enable"], False):
            return False
        wt = self.getValue(["Makeup Weight"], 0)

        if wt == 0:
            return

        from daz_import.Elements.ShaderGroup import MakeupShaderGroup
        self.column += 1

        node = self.addGroup(MakeupShaderGroup, "DAZ Makeup", size=100)

        color, tex = self.getColorTex(
            ["Makeup Base Color"], "COLOR", ColorStatic.WHITE, False)

        self.linkColor(tex, node, color, "Color")
        roughness, roughtex = self.getColorTex(
            ["Makeup Roughness Mult"], "NONE", 0.0, False)
        self.linkScalar(roughtex, node, roughness, "Roughness")
        self.linkBumpNormal(node)

        wt, wttex = self.getColorTex(["Makeup Weight"], "NONE", 0.0, False)
        self.mixWithActive(wt, wttex, node)

        return True

# -------------------------------------------------------------
#  Dual Lobe
# -------------------------------------------------------------

    def buildDualLobe(self):
        from daz_import.Elements.ShaderGroup import DualLobeUberIrayShaderGroup, DualLobePBRSkinShaderGroup

        if not self.isEnabled("Dual Lobe Specular"):
            return

        self.column += 1
        if self.material.shader == 'PBRSKIN':
            node = self.addGroup(DualLobePBRSkinShaderGroup,
                                 "DAZ Dual Lobe PBR", size=100)
        else:
            node = self.addGroup(DualLobeUberIrayShaderGroup,
                                 "DAZ Dual Lobe Uber", size=100)
        value, tex = self.getColorTex(
            ["Dual Lobe Specular Weight"], "NONE", 0.5, False)
        node.inputs["Weight"].default_value = value
        if tex:
            wttex = self.multiplyScalarTex(value, tex)

            if wttex:
                self.links.new(wttex.outputs[0], node.inputs["Weight"])

        value, tex = self.getColorTex(
            ["Dual Lobe Specular Reflectivity"], "NONE", 0.5, False)
        node.inputs["IOR"].default_value = 1.1 + 0.7*value

        if tex:
            iortex = self.multiplyAddScalarTex(0.7*value, 1.1, tex)
            self.links.new(iortex.outputs[0], node.inputs["IOR"])

        ratio = self.getValue(["Dual Lobe Specular Ratio"], 1.0)

        if self.material.shader == 'PBRSKIN':
            roughness, roughtex = self.getColorTex(
                ["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
            lobe2mult = self.getValue(["Specular Lobe 2 Roughness Mult"], 1.0)
            duallobemult = self.getValue(
                ["Dual Lobe Specular Roughness Mult"], 1.0)
            self.setRoughness(node, "Roughness 1",
                              roughness*duallobemult, roughtex)
            self.setRoughness(node, "Roughness 2", roughness *
                              duallobemult*lobe2mult, roughtex)
            ratio = 1 - ratio
        else:
            roughness1, roughtex1 = self.getColorTex(
                ["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
            self.setRoughness(node, "Roughness 1", roughness1, roughtex1)
            roughness2, roughtex2 = self.getColorTex(
                ["Specular Lobe 2 Roughness"], "NONE", 0.0, False)
            self.setRoughness(node, "Roughness 2", roughness2, roughtex2)

        self.linkBumpNormal(node)
        self.mixWithActive(ratio, None, node, keep=True)
        Settings.usedFeatures_["Glossy"] = True

    def getGlossyColor(self):
        #   glossy bsdf color = iray glossy color * iray glossy layered weight
        strength, strtex = self.getColorTex(
            "getChannelGlossyLayeredWeight", "NONE", 1.0, False)
        color, tex = self.getColorTex(
            "getChannelGlossyColor", "COLOR", ColorStatic.WHITE, False)

        if tex and strtex:
            tex = self.mixTexs('MULTIPLY', tex, strtex)
        elif strtex:
            tex = strtex

        color = strength*color

        if tex:
            tex = self.multiplyVectorTex(color, tex)

        return color, tex

    def buildGlossy(self):
        color = self.getColor("getChannelGlossyColor", ColorStatic.BLACK)
        strength = self.getValue("getChannelGlossyLayeredWeight", 0)
        if ColorStatic.isBlack(color) or strength == 0:
            return

        from daz_import.Elements.ShaderGroup import FresnelShaderGroup
        fresnel = self.addGroup(FresnelShaderGroup, "DAZ Fresnel")
        ior, iortex = self.getFresnelIOR()
        self.linkScalar(iortex, fresnel, ior, "IOR")
        self.linkBumpNormal(fresnel)
        self.fresnel = fresnel

        #   glossy bsdf roughness = iray glossy roughness ^ 2
        channel, invert = self.material.getChannelGlossiness()
        invert = not invert             # roughness = invert glossiness
        value = UtilityStatic.clamp(
            self.material.channelsData.getChannelValue(channel, 0.0))

        if invert:
            roughness = (1-value)
        else:
            roughness = value

        fnroughness = roughness**2

        if bpy.app.version < (2, 80):
            roughness = roughness**2
            value = value**2

        from daz_import.Elements.ShaderGroup import GlossyShaderGroup
        self.column += 1
        glossy = self.addGroup(GlossyShaderGroup, "DAZ Glossy", size=100)
        color, tex = self.getGlossyColor()

        self.linkColor(tex, glossy, color, "Color")

        roughtex = self.addSlot(
            channel, glossy, "Roughness", roughness, value, invert)
        self.linkBumpNormal(glossy)
        self.linkScalar(roughtex, fresnel, fnroughness, "Roughness")

        Settings.usedFeatures_["Glossy"] = True
        self.mixWithActive(1.0, self.fresnel, glossy)

    def getFresnelIOR(self):
        #   fresnel ior = 1.1 + iray glossy reflectivity * 0.7
        #   fresnel ior = 1.1 + iray glossy specular / 0.078
        ior = 1.45
        iortex = None

        if self.material.shader == 'UBER_IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                value, tex = self.getColorTex(
                    "getChannelGlossyReflectivity", "NONE", 0, False)
                factor = 0.7 * value
            elif self.material.basemix == 1:  # Specular/Glossiness
                color, tex = self.getColorTex(
                    "getChannelGlossySpecular", "COLOR", ColorStatic.WHITE, False)
                factor = 0.7 * VectorStatic.color(color) / 0.078

            ior = 1.1 + factor

            if tex:
                iortex = self.multiplyAddScalarTex(factor, 1.1, tex)
        return ior, iortex

# -------------------------------------------------------------
#   Top Coat
# -------------------------------------------------------------

    def buildTopCoat(self):
        if not self.isEnabled("Top Coat"):
            return

        topweight = self.getValue(["Top Coat Weight"], 0)

        if topweight == 0:
            return

        # Top Coat Layering Mode
        #   [ "Reflectivity", "Weighted", "Fresnel", "Custom Curve" ]
        lmode = self.getValue(["Top Coat Layering Mode"], 0)
        fresnel = refltex = None
        if lmode == 2:  # Fresnel
            from daz_import.Elements.ShaderGroup import FresnelShaderGroup
            weight = 0.5
            fresnel = self.addGroup(FresnelShaderGroup, "DAZ Fresnel")
            ior, iortex = self.getColorTex(["Top Coat IOR"], "NONE", 1.45)
            self.linkScalar(iortex, fresnel, ior, "IOR")

        if self.material.shader == 'UBER_IRAY':
            # Top Coat Bump Mode
            #   [ "Height Map", "Normal Map" ]
            if not fresnel:
                refl, refltex = self.getColorTex(
                    ["Reflectivity"], "NONE", 0, useFactor=False)
                weight = 0.05 * topweight * refl
            bump, bumptex = self.getColorTex(
                ["Top Coat Bump"], "NONE", 0, useFactor=False)
        else:
            if not fresnel:
                refl, refltex = self.getColorTex(
                    ["Top Coat Reflectivity"], "NONE", 0, useFactor=False)
            weight = 0.05 * topweight * refl
            bump = self.getValue(["Top Coat Bump Weight"], 0)
            bump *= self.bumpval
            bumptex = None

        _, tex = self.getColorTex(["Top Coat Weight"], "NONE", 0, value=weight)
        weighttex = self.multiplyTexs(tex, refltex)
        color, coltex = self.getColorTex(
            ["Top Coat Color"], "COLOR", ColorStatic.WHITE)
        roughness, roughtex = self.getColorTex(
            ["Top Coat Roughness"], "NONE", 0)
        if roughness == 0:
            glossiness, glosstex = self.getColorTex(
                ["Top Coat Glossiness"], "NONE", 1)
            roughness = 1 - glossiness**2
            roughtex = self.invertTex(glosstex, 5)

        from daz_import.Elements.ShaderGroup import TopCoatShaderGroup
        self.column += 1
        top = self.addGroup(TopCoatShaderGroup, "DAZ Top Coat", size=100)
        self.linkColor(coltex, top, color, "Color")
        self.linkScalar(roughtex, top, roughness, "Roughness")
        if self.material.shader == 'PBRSKIN':
            if self.bumptex:
                self.links.new(self.bumptex.outputs[0], top.inputs["Height"])
                self.material.addGeoBump(self.bumptex, top.inputs["Distance"])
            self.linkNormal(top)
        elif bumptex:
            self.links.new(bumptex.outputs[0], top.inputs["Height"])
            self.material.addGeoBump(bumptex, top.inputs["Distance"])
            self.linkBumpNormal(top)
        top.inputs["Bump"].default_value = bump * Settings.bumpFactor
        self.mixWithActive(weight, weighttex, top)
        if fresnel:
            self.linkScalar(roughtex, fresnel, roughness, "Roughness")
            self.linkBumpNormal(fresnel)
            self.links.new(fresnel.outputs[0], top.inputs["Fac"])

# -------------------------------------------------------------
#   Translucency
# -------------------------------------------------------------

    def checkTranslucency(self):
        if not self.isEnabled("Translucency"):
            return False
        if (self.material.thinWall or
            self.volume or
                self.material.translucent):
            return True
        if (self.material.refractive or
                not self.material.translucent):
            return False

    def buildTranslucency(self):
        if (Settings.materialMethod != 'BSDF' or
                not self.checkTranslucency()):
            return
        fac = self.getValue("getChannelTranslucencyWeight", 0)
        effect = self.getValue(["Base Color Effect"], 0)
        if fac == 0 and effect != 1:
            return
        self.column += 1
        mat = self.material.rna
        color, tex = self.getTranslucentColor()

        if ColorStatic.isBlack(color):
            return

        from daz_import.Elements.ShaderGroup import TranslucentShaderGroup

        node = self.addGroup(TranslucentShaderGroup,
                             "DAZ Translucent", size=200)
        node.width = 200
        self.linkColor(tex, node, color, "Color")
        node.inputs["Gamma"].default_value = 3.5
        node.inputs["Scale"].default_value = 1.0
        ssscolor, ssstex, sssmode = self.getSSSColor()
        radius, radtex = self.getSSSRadius(color, ssscolor, ssstex, sssmode)
        self.linkColor(radtex, node, radius, "Radius")
        node.inputs["Cycles Mix Factor"].default_value = (
            not Settings.useVolume)
        node.inputs["Eevee Mix Factor"].default_value = 1.0
        self.linkBumpNormal(node)

        fac, factex = self.getColorTex(
            "getChannelTranslucencyWeight", "NONE", 0)
        if effect == 1:  # Scatter and transmit
            fac = 0.5 + fac/2
            if factex and factex.type == 'MATH':
                factex.inputs[0].default_value = fac
        self.mixWithActive(fac, factex, node)
        Settings.usedFeatures_["Transparent"] = True
        self.endSSS()

    def getTranslucentColor(self):
        color, tex = self.getColorTex(
            ["Translucency Color"], "COLOR", ColorStatic.BLACK)
        if (tex is None and
                (Settings.useFakeTranslucencyTexture or not Settings.useVolume)):
            tex = self.diffuseTex
        return color, tex

    def getSSSColor(self):
        sssmode = self.getValue(["SSS Mode"], 0)
        # [ "Mono", "Chromatic" ]
        if sssmode == 1:
            color, tex = self.getColorTex(
                "getChannelSSSColor", "COLOR", ColorStatic.BLACK)
        elif sssmode == 0:
            sss, tex = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            if sss > 1:
                sss = 1
            color = (sss, sss, sss)
        else:
            color, tex = ColorStatic.WHITE, None
        return color, tex, sssmode

    def endSSS(self):
        Settings.usedFeatures_["SSS"] = True
        mat = self.material.rna
        if hasattr(mat, "use_sss_translucency"):
            mat.use_sss_translucency = True

    def getSSSRadius(self, color, ssscolor, ssstex, sssmode):
        # if there's no volume we use the sss to make translucency
        # please note that here we only use the iray base translucency color with no textures
        # as for blender 2.8x eevee doesn't support nodes in the radius channel so we deal with it
        if self.material.thinWall:
            return color, None

        if sssmode == 1 and ColorStatic.isWhite(ssscolor):
            ssscolor = ColorStatic.BLACK
        elif sssmode == 0:  # Mono
            s, ssstex = self.getColorTex("getChannelSSSAmount", "NONE", 0)
            if s > 1:
                s = 1
            ssscolor = Vector((s, s, s))
        trans, transtex = self.getColorTex(
            ["Transmitted Color"], "COLOR", ColorStatic.BLACK)
        if ColorStatic.isWhite(trans):
            trans = ColorStatic.BLACK

        rad, radtex = self.sumColors(ssscolor, ssstex, trans, transtex)
        radius = rad * 2.0 * Settings.scale_
        return radius, radtex

# -------------------------------------------------------------
#   Transparency
# -------------------------------------------------------------

    def sumColors(self, color, tex, color2, tex2):
        if tex and tex2:
            tex = self.mixTexs('ADD', tex, tex2)
        elif tex2:
            tex = tex2
        color = Vector(color) + Vector(color2)
        return color, tex

    def multiplyColors(self, color, tex, color2, tex2):
        if tex and tex2:
            tex = self.mixTexs('MULTIPLY', tex, tex2)
        elif tex2:
            tex = tex2
        color = self.compProd(color, color2)
        return color, tex

    def getRefractionColor(self):
        if self.material.shareGlossy:
            color, tex = self.getColorTex(
                "getChannelGlossyColor", "COLOR", ColorStatic.WHITE)
            roughness, roughtex = self.getColorTex(
                "getChannelGlossyRoughness", "NONE", 0, False, maxval=1)
        else:
            color, tex = self.getColorTex(
                "getChannelRefractionColor", "COLOR", ColorStatic.WHITE)
            roughness, roughtex = self.getColorTex(
                ["Refraction Roughness"], "NONE", 0, False, maxval=1)
        return color, tex, roughness, roughtex

    def addInput(self, node, channel, slot, colorSpace, default, maxval=0):
        value, tex = self.getColorTex(
            channel, colorSpace, default, maxval=maxval)
        if VectorStatic.is_vector(default):
            node.inputs[slot].default_value[0:3] = value
        else:
            node.inputs[slot].default_value = value
        if tex:
            self.links.new(tex.outputs[0], node.inputs[slot])
        return value, tex

    def setRoughness(self, node, slot, roughness, roughtex, square=True):
        node.inputs[slot].default_value = roughness
        if roughtex:
            tex = self.multiplyScalarTex(roughness, roughtex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return roughness

    def buildRefraction(self):
        weight, wttex = self.getColorTex(
            "getChannelRefractionWeight", "NONE", 0.0)
        if weight == 0:
            return
        node, color = self.buildRefractionNode()
        self.mixWithActive(weight, wttex, node)
        if Settings.useFakeCaustics and not self.material.thinWall:
            from daz_import.Elements.ShaderGroup import FakeCausticsShaderGroup
            self.column += 1
            node = self.addGroup(FakeCausticsShaderGroup, "DAZ Fake Caustics", args=[
                                 color], force=True)
            self.mixWithActive(weight, wttex, node, keep=True)

    def buildRefractionNode(self):
        from daz_import.Elements.ShaderGroup import RefractionShaderGroup
        self.column += 1
        node = self.addGroup(RefractionShaderGroup, "DAZ Refraction", size=150)
        node.width = 240

        color, tex = self.getColorTex(
            "getChannelGlossyColor", "COLOR", ColorStatic.WHITE)
        roughness, roughtex = self.getColorTex(
            "getChannelGlossyRoughness", "NONE", 0, False, maxval=1)
        roughness = roughness**2
        self.linkColor(tex, node, color, "Glossy Color")
        self.linkScalar(roughtex, node, roughness, "Glossy Roughness")

        color, coltex, roughness, roughtex = self.getRefractionColor()
        ior, iortex = self.getColorTex("getChannelIOR", "NONE", 1.45)
        roughness = roughness**2
        self.linkColor(coltex, node, color, "Refraction Color")
        self.linkScalar(iortex, node, ior, "Fresnel IOR")
        if self.material.thinWall:
            node.inputs["Thin Wall"].default_value = 1
            node.inputs["Refraction IOR"].default_value = 1.0
            node.inputs["Refraction Roughness"].default_value = 0.0
            self.material.setTransSettings(False, True, color, 0.1)
        else:
            node.inputs["Thin Wall"].default_value = 0
            self.linkScalar(roughtex, node, roughness, "Refraction Roughness")
            self.linkScalar(iortex, node, ior, "Refraction IOR")
            self.material.setTransSettings(True, False, color, 0.2)
        self.linkBumpNormal(node)
        return node, color

    def buildCutout(self):
        alpha, tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        if alpha < 1 or tex:
            self.column += 1
            self.useCutout = True
            if alpha == 0:
                node = self.addNode("ShaderNodeBsdfTransparent")
                self.cycles = node
                self.eevee = node
                tex = None
            else:
                from daz_import.Elements.ShaderGroup import TransparentShaderGroup
                node = self.addGroup(TransparentShaderGroup, "DAZ Transparent")
                self.mixWithActive(alpha, tex, node)
            node.inputs["Color"].default_value[0:3] = ColorStatic.WHITE
            if alpha < 1 or tex:
                self.material.setTransSettings(
                    False, False, ColorStatic.WHITE, alpha)
            Settings.usedFeatures_["Transparent"] = True

    # -------------------------------------------------------------
    #   Emission
    # -------------------------------------------------------------

    def buildEmission(self):
        if not Settings.useEmission:
            return
        color = self.getColor("getChannelEmissionColor", ColorStatic.BLACK)
        if not ColorStatic.isBlack(color):
            from daz_import.Elements.ShaderGroup import EmissionShaderGroup
            self.column += 1
            emit = self.addGroup(EmissionShaderGroup, "DAZ Emission")
            self.addEmitColor(emit, "Color")
            strength = self.getLuminance(emit)
            emit.inputs["Strength"].default_value = strength
            self.links.new(self.getCyclesSocket(), emit.inputs["Cycles"])
            self.links.new(self.getEeveeSocket(), emit.inputs["Eevee"])
            self.cycles = self.eevee = emit
            self.addOneSided()

    def addEmitColor(self, emit, slot):
        color, tex = self.getColorTex(
            "getChannelEmissionColor", "COLOR", ColorStatic.BLACK)
        if tex is None:
            _, tex = self.getColorTex(
                ["Luminance"], "COLOR", ColorStatic.BLACK)
        temp = self.getValue(["Emission Temperature"], None)
        if temp is None:
            self.linkColor(tex, emit, color, slot)
            return
        elif temp == 0:
            temp = 6500
        blackbody = self.addNode("ShaderNodeBlackbody", self.column-2)
        blackbody.inputs["Temperature"].default_value = temp
        if ColorStatic.isWhite(color) and tex is None:
            self.links.new(blackbody.outputs["Color"], emit.inputs[slot])
        else:
            mult = self.addNode("ShaderNodeMixRGB", self.column-1)
            mult.blend_type = 'MULTIPLY'
            mult.inputs[0].default_value = 1
            self.links.new(blackbody.outputs["Color"], mult.inputs[1])
            self.linkColor(tex, mult, color, 2)
            self.links.new(mult.outputs[0], emit.inputs[slot])

    def getLuminance(self, emit):
        lum = self.getValue(["Luminance"], 1500)
        # "cd/m^2", "kcd/m^2", "cd/ft^2", "cd/cm^2", "lm", "W"
        units = self.getValue(["Luminance Units"], 3)
        factors = [1, 1000, 10.764, 10000, 1, 1]
        strength = lum/2 * factors[units] / 15000
        if units >= 4:
            self.material.geoemit.append(emit.inputs["Strength"])
            if units == 5:
                strength *= self.getValue(["Luminous Efficacy"], 1)
        return strength

    def addOneSided(self):
        twosided = self.getValue(["Two Sided Light"], False)
        if not twosided:
            from daz_import.Elements.ShaderGroup import OneSidedShaderGroup
            node = self.addGroup(OneSidedShaderGroup,
                                 "DAZ VectorStatic.one-Sided")
            self.links.new(self.getCyclesSocket(), node.inputs["Cycles"])
            self.links.new(self.getEeveeSocket(), node.inputs["Eevee"])
            self.cycles = self.eevee = node

    # -------------------------------------------------------------
    #   Volume
    # -------------------------------------------------------------

    def invertColor(self, color, tex, col):
        inverse = (1-color[0], 1-color[1], 1-color[2])
        return inverse, self.invertTex(tex, col)

    def buildVolume(self):
        if (self.material.thinWall or
            Settings.materialMethod != "BSDF" or
                not Settings.useVolume):
            return
        self.volume = None
        if self.isEnabled("Translucency"):
            transcolor, transtex = self.getColorTex(
                ["Transmitted Color"], "COLOR", ColorStatic.BLACK)
            sssmode, ssscolor, ssstex = self.getSSSInfo(transcolor)
            if self.isEnabled("Transmission"):
                self.buildVolumeTransmission(transcolor, transtex)
            if self.isEnabled("Subsurface"):
                self.buildVolumeSubSurface(sssmode, ssscolor, ssstex)
        if self.volume:
            self.volume.width = 240
            Settings.usedFeatures_["Volume"] = True

    def getSSSInfo(self, _):
        if self.material.shader == 'UBER_IRAY':
            sssmode = self.getValue(["SSS Mode"], 0)
        elif self.material.shader == 'PBRSKIN':
            sssmode = 1
        else:
            sssmode = 0

        # [ "Mono", "Chromatic" ]

        if sssmode == 1:
            ssscolor, ssstex = self.getColorTex(
                "getChannelSSSColor", "COLOR", ColorStatic.BLACK)
            return 1, ssscolor, ssstex
        else:
            return 0, ColorStatic.WHITE, None

    def buildVolumeTransmission(self, transcolor, transtex):
        from daz_import.Elements.ShaderGroup import VolumeShaderGroup

        dist = self.getValue(["Transmitted Measurement Distance"], 0.0)

        if ColorStatic.isBlack(transcolor) or ColorStatic.isWhite(transcolor) or dist == 0.0:
            return

        self.volume = self.addGroup(VolumeShaderGroup, "DAZ Volume")
        self.volume.inputs["Absorbtion Density"].default_value = 100/dist
        self.linkColor(transtex, self.volume,
                       transcolor, "Absorbtion Color")

    def buildVolumeSubSurface(self, sssmode, ssscolor, ssstex):
        from daz_import.Elements.ShaderGroup import VolumeShaderGroup
        if self.material.shader == 'UBER_IRAY':
            factor = 50
        else:
            factor = 25

        sss = self.getValue(["SSS Amount"], 0.0)
        dist = self.getValue("getChannelScatterDist", 0.0)

        if not (sssmode == 0 or ColorStatic.isBlack(ssscolor) or ColorStatic.isWhite(ssscolor) or dist == 0.0):
            color, tex = self.invertColor(ssscolor, ssstex, 6)
            if self.volume is None:
                self.volume = self.addGroup(VolumeShaderGroup, "DAZ Volume")
            self.linkColor(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = factor/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue([
                                                                                   "SSS Direction"], 0)
        elif sss > 0 and dist > 0.0:
            if self.volume is None:
                self.volume = self.addGroup(VolumeShaderGroup, "DAZ Volume")
            sss, tex = self.getColorTex(["SSS Amount"], "NONE", 0.0)
            color = (sss, sss, sss)
            self.linkColor(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = factor/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue([
                                                                                   "SSS Direction"], 0)

    # -------------------------------------------------------------
    #   Output
    # -------------------------------------------------------------

    def buildOutput(self):
        self.column += 1
        output = self.addNode("ShaderNodeOutputMaterial")
        output.target = 'ALL'

        if self.cycles:
            self.links.new(self.getCyclesSocket(), output.inputs["Surface"])

        if self.volume and not self.useCutout:
            self.links.new(self.volume.outputs[0], output.inputs["Volume"])

        if self.displacement:
            self.links.new(self.displacement, output.inputs["Displacement"])

        if self.liegroups:
            node = self.addNode("ShaderNodeValue", col=self.column-1)
            node.outputs[0].default_value = 1.0
            for lie in self.liegroups:
                self.links.new(node.outputs[0], lie.inputs["Alpha"])

        if self.volume or self.eevee:
            output.target = 'CYCLES'
            outputEevee = self.addNode("ShaderNodeOutputMaterial")
            outputEevee.target = 'EEVEE'
            if self.eevee:
                self.links.new(self.getEeveeSocket(),
                               outputEevee.inputs["Surface"])
            elif self.cycles:
                self.links.new(self.getCyclesSocket(),
                               outputEevee.inputs["Surface"])
            if self.displacement:
                self.links.new(self.displacement,
                               outputEevee.inputs["Displacement"])

    def buildDisplacementNodes(self):
        channel = self.material.getChannelDisplacement()
        if not(channel and
                self.isEnabled("Displacement") and
                Settings.useDisplacement):
            return
        tex = self.addTexImageNode(channel, "NONE")
        if tex:
            strength = self.material.getChannelValue(channel, 1)
            if strength == 0:
                return
            dmin = self.getValue("getChannelDispMin", -0.05)
            dmax = self.getValue("getChannelDispMax", 0.05)
            if dmin > dmax:
                tmp = dmin
                dmin = dmax
                dmax = tmp

            from daz_import.Elements.ShaderGroup import DisplacementShaderGroup
            node = self.addGroup(DisplacementShaderGroup, "DAZ Displacement")
            self.links.new(tex.outputs[0], node.inputs["Texture"])
            node.inputs["Strength"].default_value = strength
            node.inputs["Max"].default_value = Settings.scale_ * dmax
            node.inputs["Min"].default_value = Settings.scale_ * dmin
            self.linkNormal(node)
            self.displacement = node.outputs["Displacement"]
            mat = self.material.rna
            mat.cycles.displacement_method = 'BOTH'

    def addSingleTexture(self, col, asset, map, colorSpace):
        isnew = False
        img = asset.buildCycles(colorSpace)
        if img:
            imgname = img.name
        else:
            imgname = asset.getName()
        hasMap = asset.hasMapping(map)
        texnode = self.getTexNode(imgname, colorSpace)
        if not hasMap and texnode:
            return texnode, False
        else:
            texnode = self.addTextureNode(col, img, imgname, colorSpace)
            isnew = True
            if not hasMap:
                self.setTexNode(imgname, texnode, colorSpace)
        return texnode, isnew

    def addTextureNode(self, col, img, imgname, colorSpace) -> ShaderNodeTexImage:
        node = self.addNode("ShaderNodeTexImage", col)

        node.image = img
        node.interpolation = Settings.imageInterpolation
        node.label = imgname.rsplit("/", 1)[-1]

        self.setColorSpace(node, colorSpace)
        node.name = imgname

        if hasattr(node, "image_user"):
            node.image_user.frame_duration = 1
            node.image_user.frame_current = 1

        return node

    @staticmethod
    def setColorSpace(node, colorSpace):
        if hasattr(node, "color_space"):
            node.color_space = colorSpace

    def addImageTexNode(self, filepath: str, tname, col) -> ShaderNodeTexImage:
        img = bpy.data.images.load(filepath)
        img.name = os.path.splitext(os.path.basename(filepath))[0]
        img.colorspace_settings.name = "Non-Color"
        return self.addTextureNode(col, img, tname, "NONE")

    def getTexNode(self, key, colorSpace):
        if key in self.texnodes.keys():
            for texnode, colorSpace1 in self.texnodes[key]:
                if colorSpace1 == colorSpace:
                    return texnode
        return None

    def setTexNode(self, key, texnode, colorSpace):
        if key not in self.texnodes.keys():
            self.texnodes[key] = []
        self.texnodes[key].append((texnode, colorSpace))

    def linkVector(self, texco, node, slot="Vector"):
        if not texco:
            return

        if (isinstance(texco, bpy.types.NodeSocketVector) or
                isinstance(texco, bpy.types.NodeSocketFloat)):
            self.links.new(texco, node.inputs[slot])
            return

        if "Vector" in texco.outputs.keys():
            self.links.new(texco.outputs["Vector"], node.inputs[slot])
        else:
            self.links.new(texco.outputs["UV"], node.inputs[slot])

    def addTexImageNode(self, channel, colorSpace=None):
        col = self.column-2
        textures, maps = self.material.getTextures(channel)

        if len(textures) != len(maps):
            print(textures, '\n', maps)
            raise DazError("Bug: Num assets != num maps")
        elif len(textures) == 0:
            return None
        elif len(textures) == 1:
            texnode, isnew = self.addSingleTexture(
                col, textures[0], maps[0], colorSpace)
            if isnew:
                self.linkVector(self.texco, texnode)
            return texnode

        from daz_import.Elements.ShaderGroup import LieShaderGroup

        node = self.addNode("ShaderNodeGroup", col)
        node.width = 240

        try:
            name = os.path.basename(textures[0].map.url)
        except:
            name = "Group"

        group = LieShaderGroup()
        group.create(node, name, self)
        self.linkVector(self.texco, node)
        group.addTextureNodes(textures, maps, colorSpace)

        node.inputs["Alpha"].default_value = 1
        self.liegroups.append(node)

        return node

    def mixTexs(self, op, tex1, tex2, slot1=0, slot2=0, color1=None, color2=None, fac=1, factex=None):

        if fac < 1 or factex:
            pass
        elif tex1 is None:
            return tex2
        elif tex2 is None:
            return tex1

        mix = self.addNode("ShaderNodeMixRGB", self.column-1)
        mix.blend_type = op
        mix.use_alpha = False
        mix.inputs[0].default_value = fac

        if factex:
            self.links.new(factex.outputs[0], mix.inputs[0])

        if color1:
            mix.inputs[1].default_value[0:3] = color1

        if tex1:
            self.links.new(tex1.outputs[slot1], mix.inputs[1])

        if color2:
            mix.inputs[2].default_value[0:3] = color2

        if tex2:
            self.links.new(tex2.outputs[slot2], mix.inputs[2])

        return mix

    def mixWithActive(self, fac, tex, shader, useAlpha=False, keep=False):
        if shader.type != 'GROUP':
            raise RuntimeError("BUG: mixWithActive", shader.type)
        if fac == 0 and tex is None and not keep:
            return
        elif fac == 1 and tex is None and not keep:
            shader.inputs["Fac"].default_value = fac
            self.cycles = shader
            self.eevee = shader
            return
        if self.eevee:
            self.makeActiveMix(
                "Eevee", self.eevee, self.getEeveeSocket(), fac, tex, shader, useAlpha)
        self.eevee = shader
        if self.cycles:
            self.makeActiveMix(
                "Cycles", self.cycles, self.getCyclesSocket(), fac, tex, shader, useAlpha)
        self.cycles = shader

    def makeActiveMix(self, slot, active, socket, fac, tex, shader, useAlpha):
        self.links.new(socket, shader.inputs[slot])
        shader.inputs["Fac"].default_value = fac
        if tex:
            if useAlpha and "Alpha" in tex.outputs.keys():
                texsocket = tex.outputs["Alpha"]
            else:
                texsocket = tex.outputs[0]
            self.links.new(texsocket, shader.inputs["Fac"])

    def linkColor(self, tex, node, color, slot=0):
        node.inputs[slot].default_value[0:3] = color
        if tex:
            tex = self.multiplyVectorTex(color, tex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex

    def linkScalar(self, tex, node, value, slot):
        node.inputs[slot].default_value = value
        if tex:
            tex = self.multiplyScalarTex(value, tex)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex

    def addSlot(self, channel, node, slot, value, value0, invert):
        node.inputs[slot].default_value = value
        tex = self.addTexImageNode(channel, "NONE")
        if tex:
            tex = self.fixTex(tex, value0, invert)
            if tex:
                self.links.new(tex.outputs[0], node.inputs[slot])
        return tex

    def fixTex(self, tex, value, invert):
        _, tex = self.multiplySomeTex(value, tex)
        if invert:
            return self.invertTex(tex, 3)
        else:
            return tex

    def invertTex(self, tex, col):
        if tex:
            inv = self.addNode("ShaderNodeInvert", col)
            self.links.new(tex.outputs[0], inv.inputs["Color"])
            return inv
        else:
            return None

    def multiplySomeTex(self, value, tex, slot=0):
        if isinstance(value, float) or isinstance(value, int):
            if tex and value != 1:
                tex = self.multiplyScalarTex(value, tex, slot)
        elif tex:
            tex = self.multiplyVectorTex(value, tex, slot)
        return value, tex

    def multiplyVectorTex(self, color, tex, slot=0, col=None):
        if ColorStatic.isWhite(color):
            return tex
        elif ColorStatic.isBlack(color):
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1
        mix = self.addNode("ShaderNodeMixRGB", col)
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value[0:3] = color
        self.links.new(tex.outputs[0], mix.inputs[2])
        return mix

    def multiplyScalarTex(self, value, tex, slot=0, col=None):
        if value == 1:
            return tex
        elif value == 0:
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1
        mult = self.addNode("ShaderNodeMath", col)
        mult.operation = 'MULTIPLY'
        mult.inputs[0].default_value = value
        self.links.new(tex.outputs[slot], mult.inputs[1])
        return mult

    def multiplyAddScalarTex(self, factor, term, tex, slot=0, col=None):
        if col is None:
            col = self.column-1
        mult = self.addNode("ShaderNodeMath", col)
        try:
            mult.operation = 'MULTIPLY_ADD'
            ok = True
        except TypeError:
            ok = False
        if ok:
            self.links.new(tex.outputs[slot], mult.inputs[0])
            mult.inputs[1].default_value = factor
            mult.inputs[2].default_value = term
            return mult
        else:
            mult.operation = 'MULTIPLY'
            self.links.new(tex.outputs[slot], mult.inputs[0])
            mult.inputs[1].default_value = factor
            add = self.addNode("ShaderNodeMath", col)
            add.operation = 'ADD'
            add.inputs[1].default_value = term
            self.links.new(mult.outputs[slot], add.inputs[0])
            return add

    def multiplyTexs(self, tex1, tex2):
        if tex1 and tex2:
            mult = self.addNode("ShaderNodeMath")
            mult.operation = 'MULTIPLY'
            self.links.new(tex1.outputs[0], mult.inputs[0])
            self.links.new(tex2.outputs[0], mult.inputs[1])
            return mult
        elif tex1:
            return tex1
        else:
            return tex2

    def selectDiffuse(self, marked):
        if self.diffuseTex and marked[self.diffuseTex.name]:
            self.diffuseTex.select = True
            self.nodes.active = self.diffuseTex

    def getLink(self, node, slot):
        for link in self.links:
            if (link.to_node == node and
                    link.to_socket.name == slot):
                return link
        return None

    def removeLink(self, node, slot):
        link = self.getLink(node, slot)
        if link:
            self.links.remove(link)

    def replaceSlot(self, node, slot, value):
        node.inputs[slot].default_value = value
        self.removeLink(node, slot)

    def findTexco(self, col):
        if nodes := self.findNodes("TEX_COORD"):
            return nodes[0]
        else:
            return self.addNode("ShaderNodeTexCoord", col)

    def findNodes(self, nodeType):
        nodes = []
        for node in self.nodes.values():
            if node.type == nodeType:
                nodes.append(node)
        return nodes

    @classmethod
    def create_shader(cls, mat: BlenderMaterial) -> CyclesShader:
        shader = cls(None)

        shader.nodes = mat.node_tree.nodes
        shader.links = mat.node_tree.links

        return shader

    
    def findNode(self, key):
        return super().findNode(self, key)

# -------------------------------------------------------------
#   Utilities
# -------------------------------------------------------------
