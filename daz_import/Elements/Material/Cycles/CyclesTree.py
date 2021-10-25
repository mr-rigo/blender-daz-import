from __future__ import annotations
import os
from typing import Type, Dict, List, Tuple
from mathutils import Vector

import bpy

from bpy.types import Material as BlenderMaterial
from bpy.types import ShaderNode, NodeLink, \
    ShaderNodeTexImage, ShaderNodeBump, NodeSocketVector,\
    ShaderNodeGroup, ShaderNodeTexImage, ShaderNodeMapping, ShaderNodeGroup, ShaderNodeMixRGB, ShaderNodeUVMap


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

    def __init__(self, material: Material, b_mat: BlenderMaterial = None):
        self.shader_graph = ShaderGraph()
        self.material: Material = material
        self.easy_shader = False
        self.ycoords = self.NCOLUMNS * [2 * self.YSIZE]
        self.cycles: ShaderNodeGroup = None
        self.eevee: ShaderNodeGroup = None
        self.column = 4

        self.texnodes: Dict[str, BlenderMaterial] = {}

        # self.nodes: List[ShaderNode] = []
        self.links: List[NodeLink] = None

        self.group = None
        self.groups = {}
        self.liegroups = []

        self._diffuse_tex: ShaderNodeTexImage = None
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

        if b_mat:
            self.set_material(b_mat)

    # Node
    def link(self, a, b):
        return self.shader_graph.links.new(a, b)

    def __repr__(self):
        return ("<Cycles %s %s %s>" % (self.material.rna, self.shader_graph.nodes, self.shader_graph.links))

    # Material
    def getValue(self, channel, default):
        return self.material.channelsData.getValue(channel, default)

    # Material
    def is_enabled(self, key) -> bool:
        return self.material.enabled.get(key)

    # Material
    def get_color(self, channel, default):
        return self.material.get_color(channel, default)

    # ShaderGraph
    def add_node(self, stype, col=None, size=0, label=None, parent=None) -> ShaderNode:
        if col is None:
            col = self.column

        node = self.shader_graph.nodes.new(type=stype)

        node.location = ((col-2)*self.XSIZE, self.ycoords[col])
        self.ycoords[col] -= (self.YSIZE + size)

        if label:
            node.label = label

        if parent:
            node.parent = parent

        return node

    # ShaderGraph
    def _get_texco(self, uv: str) -> NodeSocketVector:
        key = self.material.getUvKey(uv, self.texcos)

        if key is None:
            return self.texco

        if key not in self.texcos.keys():
            self._add_uv_node(key, key)

        return self.texcos.get(key)

    # ShaderGraph 7
    def cycles_socket(self):
        if out := self.cycles.outputs.get("Cycles"):
            return out
        else:
            return self.cycles.outputs[0]

    # ShaderGraph 6
    def eevee_socket(self):
        if out := self.eevee.outputs.get("Eevee"):
            return out
        else:
            return self.eevee.outputs[0]

    # Node 29
    def add_group(self, cls: Type, name, col=None,
                  size=0, args=[], force=False):
        from daz_import.Elements.ShaderGroup import ShaderGroup

        if col is None:
            col = self.column

        node = self.add_node("ShaderNodeGroup", col, size=size)
        group: ShaderGroup = cls()

        if name in bpy.data.node_groups.keys() and not force:
            tree = bpy.data.node_groups.get(name)
            if group.mat_group.checkSockets(tree):
                node.node_tree = tree
                return node

        group.create(node, name, self)
        group.addNodes(args)

        return node

    # ShaderGraph / Node 1
    def _add_shell_group(self, shell, push) -> ShaderNodeGroup:
        from daz_import.Elements.ShaderGroup import OpaqueShellPbrGroup, RefractiveShellPbrGroup
        from daz_import.Elements.ShaderGroup import OpaqueShellCyclesGroup, RefractiveShellCyclesGroup

        shmat = shell.material

        shmat.isShellMat = True
        shname = shell.name

        if shmat.getValue("getChannelCutoutOpacity", 1) == 0 or \
                shmat.getValue("getChannelOpacity", 1) == 0:
            print("Invisible shell %s for %s" % (shname, self.material.name))
            return

        nname = f"{shname}_{self.material.name}"

        node = self.add_node("ShaderNodeGroup")

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
            if shmat.refractive:
                group = RefractiveShellCyclesGroup(push)
            else:
                group = OpaqueShellCyclesGroup(push)
        elif self.type == 'PBR':
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

    # ShaderGraph
    def build(self):
        self._build_shader()
        if self.easy_shader:
            self._easy_build()
            return

        self._build_layer()
        self._build_cutout()
        self._build_volume()
        self._build_displacement_nodes()
        self._build_shells()
        self._build_output()

    # ShaderGraph
    def _easy_build(self):
        graph = self.shader_graph

        graph.clear()
        graph.use_nodes()

        output = graph.get_output()

        shader = DiffuseShader(graph)

        # shader.diffuse.default((1, 1, 1, 1))
        # shader.specular.default(0.2)

        output.surface += shader.output

        _, diffuse = self._get_diffuse_color()

        if diffuse:
            shader.diffuse += diffuse.outputs['Color']

        # _get_glossy_color
        # _get_translucent_color
        # _get_refraction_color

    # ShaderGraph 1
    def _build_shells(self):
        shells = []
        i = 0

        for shell in self.material.shells.values():
            for geonode in shell.geometry.nodes.values():
                shells.append((geonode.push, i, shell))
                i += 1

        shells.sort()

        if shells:
            self.column += 1

        for push, i, shell in shells:
            node = self._add_shell_group(shell, push)
            if not node:
                continue

            self.link(self.cycles_socket(), node.inputs["Cycles"])
            self.link(self.eevee_socket(), node.inputs["Eevee"])
            self.link(self._get_texco(shell.uv), node.inputs["UV"])

            if self.displacement:
                self.link(self.displacement,
                          node.inputs["Displacement"])

            self.cycles = self.eevee = node

            self.displacement = node.outputs["Displacement"]
            self.ycoords[self.column] -= 50

    # ShaderGraph 8
    def _build_layer(self, uvname=''):
        self._build_normal(uvname)
        self._build_bump()
        self._build_detail(uvname)
        self._build_diffuse()

        self._build_translucency()
        self._build_makeup()
        self._build_overlay()

        if self.material.dualLobeWeight == 1:
            self._build_dual_lobe()
        elif self.material.dualLobeWeight == 0:
            self._build_glossy()
        else:
            self._build_glossy()
            self._build_dual_lobe()

        if self.material.refractive:
            self._build_refraction()

        self._build_top_coat()
        self._build_emission()

        return self.cycles

    # ShaderGraph 4
    def _build_shader(self, slot="UV"):
        mat = self.material.rna
        if not mat:
            return

        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        self.set_material(mat)

        if self.easy_shader:
            return

        return self._add_texco(slot)

    # Node 4
    def _add_texco(self, slot):
        if self.easy_shader:
            return

        if self.material.useDefaultUvs:
            node = self.add_node("ShaderNodeTexCoord", 1)
            self.texco = node.outputs[slot]
        else:
            node = self.add_node("ShaderNodeUVMap", 1)
            node.uv_map = self.material.uv_set.name
            self.texco = node.outputs["UV"]

        ox = self.getValue("getChannelHorizontalOffset", 0)
        oy = self.getValue("getChannelVerticalOffset", 0)
        kx = self.getValue("getChannelHorizontalTiles", 1)
        ky = self.getValue("getChannelVerticalTiles", 1)

        self._set_texco(ox, oy, kx, ky)

        for key, uvset in self.material.uv_sets.items():
            self._add_uv_node(key, uvset.name)

        return node

    # ShaderGraph 2
    def _add_uv_node(self, key, uvname):
        node = self.add_node("ShaderNodeUVMap", 1)
        node.uv_map = uvname

        self.texcos[key] = node.outputs["UV"]

    # ShaderGraph 2
    def _set_texco(self, ox, oy, kx, ky):
        if not(ox != 0 or oy != 0 or kx not in [0, 1] or ky not in [0, 1]):
            return

        sx = sy = 1
        dx = dy = 0

        if kx != 0:
            sx = 1/kx
            dx = -ox/kx

        if ky != 0:
            sy = 1/ky
            dy = oy/ky

        mapping = self._get_mapping_node((dx, dy, sx, sy, 0), None)

        if not mapping:
            return

        self._link_vector(self.texco, mapping, 0)
        self.texco = mapping

    # Node 2
    def _get_mapping_node(self, data, map_) -> ShaderNodeMapping:
        dx, dy, sx, sy, rz = data

        if not (sx != 1 or sy != 1 or dx != 0 or dy != 0 or rz != 0):
            return

        mapping = self.add_node("ShaderNodeMapping", 1)
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

        if map_ and not map_.invert and hasattr(mapping, "use_min"):
            mapping.use_min = mapping.use_max = 1

        return mapping

    # ShaderGraph 3
    def _build_normal(self, uvname):
        if not self.is_enabled("Normal"):
            return

        strength, tex = self._get_color_tex("getChannelNormal", "NONE", 1.0)

        if strength > 0 and tex:
            self._build_normal_map(strength, tex, uvname)

    # ShaderGraph / Node 2
    def _build_normal_map(self, strength, tex, uvname):
        self.normal = self.add_node("ShaderNodeNormalMap", col=3)
        self.normal.space = "TANGENT"

        if uvname:
            self.normal.uv_map = uvname
        elif self.material.uv_set:
            self.normal.uv_map = self.material.uv_set.name

        self.normal.inputs["Strength"].default_value = strength
        self.link(tex.outputs[0], self.normal.inputs["Color"])

    # 4
    def _build_bump(self):
        if not self.is_enabled("Bump"):
            return

        self.bumpval, self.bumptex = self._get_color_tex(
            "getChannelBump", "NONE", 0, False)

        if self.bumpval and self.bumptex:
            self.bump = self._build_bump_map(self.bumpval, self.bumptex, col=3)
            self._link_normal(self.bump)

    def _build_bump_map(self, bump, bumptex, col=3):
        node = self.add_node("ShaderNodeBump", col=col)
        node.inputs["Strength"].default_value = bump * Settings.bumpFactor
        self.link(bumptex.outputs[0], node.inputs["Height"])
        self.material.addGeoBump(bumptex, node.inputs["Distance"])
        return node

    def _link_bump_normal(self, node):
        if self.bump:
            self.link(self.bump.outputs["Normal"], node.inputs["Normal"])
        elif self.normal:
            self.link(
                self.normal.outputs["Normal"], node.inputs["Normal"])

    # def _link_bump(self, node):
    #     if self.bump:
    #         self.link(self.bump.outputs["Normal"], node.inputs["Normal"])

    def _link_normal(self, node):
        if self.normal:
            self.link(
                self.normal.outputs["Normal"], node.inputs["Normal"])

    def _build_detail(self, uvname):
        if not self.is_enabled("Detail"):
            return
        weight, wttex = self._get_color_tex(["Detail Weight"], "NONE", 0.0)
        if weight == 0:
            return
        texco = self.texco
        ox = Settings.scale_*self.getValue(["Detail Horizontal Offset"], 0)
        oy = Settings.scale_*self.getValue(["Detail Vertical Offset"], 0)
        kx = self.getValue(["Detail Horizontal Tiles"], 1)
        ky = self.getValue(["Detail Vertical Tiles"], 1)
        self._set_texco(ox, oy, kx, ky)

        strength, tex = self._get_color_tex(["Detail Normal Map"], "NONE", 1.0)
        weight = weight*strength
        mode = self.getValue(["Detail Normal Map Mode"], 0)
        # Height Map, Normal Map
        if mode == 0:
            if weight == 0:
                pass
            elif self.bump:
                link = self.getLinkTo(self, self.bump, "Height")
                if link:
                    mult = self.add_node("ShaderNodeMath", 3)
                    mult.operation = 'MULTIPLY_ADD'
                    self.link(tex.outputs[0], mult.inputs[0])
                    self.link_scalar(wttex, mult, weight, 1)
                    self.link(link.from_socket, mult.inputs[2])
                    self.link(
                        mult.outputs["Value"], self.bump.inputs["Height"])
            else:
                tex = self.multiplyTexs(tex, wttex)
                self.bump = self._build_bump_map(weight, tex, col=3)
                self._link_normal(self.bump)
        elif mode == 1:
            if weight == 0:
                pass
            elif self.normal:
                link = self.getLinkTo(self, self.normal, "Color")
                if link:
                    mix = self.add_node("ShaderNodeMixRGB", 3)
                    mix.blend_type = 'OVERLAY'
                    self.link_scalar(wttex, mix, weight, "Fac")

                    NORMAL = (0.5, 0.5, 1, 1)
                    mix.inputs["Color1"].default_value = NORMAL
                    mix.inputs["Color2"].default_value = NORMAL

                    self.link(link.from_socket, mix.inputs["Color1"])

                    if tex:
                        self.link(tex.outputs[0], mix.inputs["Color2"])
                    self.link(
                        mix.outputs["Color"], self.normal.inputs["Color"])
                else:
                    self.link(tex.outputs[0], self.normal.inputs["Color"])
            else:
                self._build_normal_map(weight, tex, uvname)
                if wttex:
                    self.link(
                        wttex.outputs[0], self.normal.inputs["Strength"])
                if self.bump:
                    self.link(
                        self.normal.outputs["Normal"], self.bump.inputs["Normal"])

        self.texco = texco

    def _get_diffuse_color(self) -> Tuple[Vector, ShaderNode]:
        color, tex = self._get_color_tex(
            "getChannelDiffuse", "COLOR", ColorStatic.WHITE)
        effect = self.getValue(["Base Color Effect"], 0)
        if effect > 0:  # Scatter Transmit, Scatter Transmit Intensity
            tint = self.get_color(["SSS Reflectance Tint"], ColorStatic.WHITE)
            color = self._comp_prod(color, tint)
        return color, tex

    def _comp_prod(self, x, y):
        return [x[0]*y[0], x[1]*y[1], x[2]*y[2]]

    def _build_diffuse(self):
        self.column = 4
        if not self.is_enabled("Diffuse"):
            return
        color, tex = self._get_diffuse_color()
        self._diffuse_tex = tex
        node = self.add_node("ShaderNodeBsdfDiffuse")
        self.cycles = self.eevee = node
        self.link_color(tex, node, color, "Color")
        roughness, roughtex = self._get_color_tex(
            ["Diffuse Roughness"], "NONE", 0, False)
        if self.is_enabled("Detail"):
            detrough, dettex = self._get_color_tex(
                ["Detail Specular Roughness Mult"], "NONE", 0, False)
            roughness *= detrough
            roughtex = self.multiplyTexs(dettex, roughtex)
        self._set_roughness(node, "Roughness", roughness, roughtex)
        self._link_bump_normal(node)
        Settings.usedFeatures_["Diffuse"] = True

    def _build_overlay(self):
        if not self.getValue(["Diffuse Overlay Weight"], 0):
            return False
        self.column += 1

        slot = self._get_image_slot(["Diffuse Overlay Weight"])

        weight, wttex = self._get_color_tex(
            ["Diffuse Overlay Weight"], "NONE", 0, slot=slot)

        if self.getValue(["Diffuse Overlay Weight Squared"], False):
            power = 4
        else:
            power = 2

        if wttex:
            wttex = self._raise_to_power(wttex, power, slot)

        color, tex = self._get_color_tex(
            ["Diffuse Overlay Color"], "COLOR", ColorStatic.WHITE)

        from daz_import.Elements.ShaderGroup import DiffuseShaderGroup

        node = self.add_group(DiffuseShaderGroup, "DAZ Overlay")

        self.link_color(tex, node, color, "Color")

        roughness, roughtex = self._get_color_tex(
            ["Diffuse Overlay Roughness"], "NONE", 0, False)

        self._set_roughness(node, "Roughness", roughness, roughtex)

        self._link_bump_normal(node)
        self.__mix_with_active(weight**power, wttex, node)

        return True

    def _get_image_slot(self, attr):
        if self.material.getImageMod(attr, "grayscale_mode") == "alpha":
            return "Alpha"
        else:
            return 0

    def _raise_to_power(self, tex, power, slot):
        node = self.add_node("ShaderNodeMath", col=self.column-1)
        node.operation = 'POWER'
        node.inputs[1].default_value = power
        if slot not in tex.outputs.keys():
            slot = 0
        self.link(tex.outputs[slot], node.inputs[0])
        return node

    def _get_color_tex(self, attr, colorSpace, default, useFactor=True, useTex=True, maxval=0, value=None, slot=0):
        channel = self.material.channelsData.getChannel(attr)
        if channel is None:
            return default, None

        if isinstance(channel, tuple):
            channel = channel[0]

        if useTex:
            tex = self._get_tex_image_node(channel, colorSpace)
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

    def _build_makeup(self):
        if not self.getValue(["Makeup Enable"], False):
            return False
        wt = self.getValue(["Makeup Weight"], 0)

        if wt == 0:
            return

        from daz_import.Elements.ShaderGroup import MakeupShaderGroup
        self.column += 1

        node = self.add_group(MakeupShaderGroup, "DAZ Makeup", size=100)

        color, tex = self._get_color_tex(
            ["Makeup Base Color"], "COLOR", ColorStatic.WHITE, False)

        self.link_color(tex, node, color, "Color")
        roughness, roughtex = self._get_color_tex(
            ["Makeup Roughness Mult"], "NONE", 0.0, False)
        self.link_scalar(roughtex, node, roughness, "Roughness")
        self._link_bump_normal(node)

        wt, wttex = self._get_color_tex(["Makeup Weight"], "NONE", 0.0, False)
        self.__mix_with_active(wt, wttex, node)

        return True

    def _build_dual_lobe(self):
        from daz_import.Elements.ShaderGroup import DualLobeUberIrayShaderGroup, DualLobePBRSkinShaderGroup

        if not self.is_enabled("Dual Lobe Specular"):
            return

        self.column += 1

        if self.material.shader_key == 'PBRSKIN':
            node = self.add_group(DualLobePBRSkinShaderGroup,
                                  "DAZ Dual Lobe PBR", size=100)
        else:
            node = self.add_group(DualLobeUberIrayShaderGroup,
                                  "DAZ Dual Lobe Uber", size=100)
        value, tex = self._get_color_tex(
            ["Dual Lobe Specular Weight"], "NONE", 0.5, False)
        node.inputs["Weight"].default_value = value

        if tex:
            if wttex := self.multiplyScalarTex(value, tex):
                self.link(wttex.outputs[0], node.inputs["Weight"])

        value, tex = self._get_color_tex(
            ["Dual Lobe Specular Reflectivity"], "NONE", 0.5, False)
        node.inputs["IOR"].default_value = 1.1 + 0.7*value

        if tex:
            iortex = self.multiplyAddScalarTex(0.7*value, 1.1, tex)
            self.link(iortex.outputs[0], node.inputs["IOR"])

        ratio = self.getValue(["Dual Lobe Specular Ratio"], 1.0)

        if self.material.shader_key == 'PBRSKIN':
            roughness, roughtex = self._get_color_tex(
                ["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
            lobe2mult = self.getValue(["Specular Lobe 2 Roughness Mult"], 1.0)
            duallobemult = self.getValue(
                ["Dual Lobe Specular Roughness Mult"], 1.0)
            self._set_roughness(node, "Roughness 1",
                              roughness*duallobemult, roughtex)
            self._set_roughness(node, "Roughness 2", roughness *
                              duallobemult*lobe2mult, roughtex)
            ratio = 1 - ratio
        else:
            roughness1, roughtex1 = self._get_color_tex(
                ["Specular Lobe 1 Roughness"], "NONE", 0.0, False)
            self._set_roughness(node, "Roughness 1", roughness1, roughtex1)
            roughness2, roughtex2 = self._get_color_tex(
                ["Specular Lobe 2 Roughness"], "NONE", 0.0, False)
            self._set_roughness(node, "Roughness 2", roughness2, roughtex2)

        self._link_bump_normal(node)
        self.__mix_with_active(ratio, None, node, keep=True)
        Settings.usedFeatures_["Glossy"] = True

    def _get_glossy_color(self):
        #   glossy bsdf color = iray glossy color * iray glossy layered weight
        strength, strtex = self._get_color_tex(
            "getChannelGlossyLayeredWeight", "NONE", 1.0, False)
        color, tex = self._get_color_tex(
            "getChannelGlossyColor", "COLOR", ColorStatic.WHITE, False)

        if tex and strtex:
            tex = self._mix_texs('MULTIPLY', tex, strtex)
        elif strtex:
            tex = strtex

        color = strength*color

        if tex:
            tex = self._multiply_vector_tex(color, tex)

        return color, tex

    def _build_glossy(self):
        from daz_import.Elements.ShaderGroup import FresnelShaderGroup
        from daz_import.Elements.ShaderGroup import GlossyShaderGroup

        color = self.get_color("getChannelGlossyColor", ColorStatic.BLACK)
        strength = self.getValue("getChannelGlossyLayeredWeight", 0)
        if ColorStatic.isBlack(color) or strength == 0:
            return

        fresnel = self.add_group(FresnelShaderGroup, "DAZ Fresnel")
        ior, iortex = self._get_fresnel_IOR()

        self.link_scalar(iortex, fresnel, ior, "IOR")

        self._link_bump_normal(fresnel)
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

        self.column += 1
        glossy = self.add_group(GlossyShaderGroup, "DAZ Glossy", size=100)
        color, tex = self._get_glossy_color()

        self.link_color(tex, glossy, color, "Color")

        roughtex = self.add_slot(
            channel, glossy, "Roughness", roughness, value, invert)
        self._link_bump_normal(glossy)
        self.link_scalar(roughtex, fresnel, fnroughness, "Roughness")

        Settings.usedFeatures_["Glossy"] = True
        self.__mix_with_active(1.0, self.fresnel, glossy)

    def _get_fresnel_IOR(self):
        #   fresnel ior = 1.1 + iray glossy reflectivity * 0.7
        #   fresnel ior = 1.1 + iray glossy specular / 0.078
        ior = 1.45
        iortex = None

        if self.material.shader_key == 'UBER_IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                value, tex = self._get_color_tex(
                    "getChannelGlossyReflectivity", "NONE", 0, False)
                factor = 0.7 * value
            elif self.material.basemix == 1:  # Specular/Glossiness
                color, tex = self._get_color_tex(
                    "getChannelGlossySpecular", "COLOR", ColorStatic.WHITE, False)
                factor = 0.7 * VectorStatic.color(color) / 0.078

            ior = 1.1 + factor

            if tex:
                iortex = self.multiplyAddScalarTex(factor, 1.1, tex)

        return ior, iortex

    # 1
    def _build_top_coat(self):
        if not self.is_enabled("Top Coat"):
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
            fresnel = self.add_group(FresnelShaderGroup, "DAZ Fresnel")
            ior, iortex = self._get_color_tex(["Top Coat IOR"], "NONE", 1.45)
            self.link_scalar(iortex, fresnel, ior, "IOR")

        if self.material.shader_key == 'UBER_IRAY':
            # Top Coat Bump Mode
            #   [ "Height Map", "Normal Map" ]
            if not fresnel:
                refl, refltex = self._get_color_tex(
                    ["Reflectivity"], "NONE", 0, useFactor=False)
                weight = 0.05 * topweight * refl
            bump, bumptex = self._get_color_tex(
                ["Top Coat Bump"], "NONE", 0, useFactor=False)
        else:
            if not fresnel:
                refl, refltex = self._get_color_tex(
                    ["Top Coat Reflectivity"], "NONE", 0, useFactor=False)
            weight = 0.05 * topweight * refl
            bump = self.getValue(["Top Coat Bump Weight"], 0)
            bump *= self.bumpval
            bumptex = None

        _, tex = self._get_color_tex(
            ["Top Coat Weight"], "NONE", 0, value=weight)
        weighttex = self.multiplyTexs(tex, refltex)
        color, coltex = self._get_color_tex(
            ["Top Coat Color"], "COLOR", ColorStatic.WHITE)
        roughness, roughtex = self._get_color_tex(
            ["Top Coat Roughness"], "NONE", 0)

        if roughness == 0:
            glossiness, glosstex = self._get_color_tex(
                ["Top Coat Glossiness"], "NONE", 1)
            roughness = 1 - glossiness**2
            roughtex = self._invert_tex(glosstex, 5)

        from daz_import.Elements.ShaderGroup import TopCoatShaderGroup

        self.column += 1
        top = self.add_group(TopCoatShaderGroup, "DAZ Top Coat", size=100)
        self.link_color(coltex, top, color, "Color")
        self.link_scalar(roughtex, top, roughness, "Roughness")

        if self.material.shader_key == 'PBRSKIN':
            if self.bumptex:
                self.link(self.bumptex.outputs[0], top.inputs["Height"])
                self.material.addGeoBump(self.bumptex, top.inputs["Distance"])
            self._link_normal(top)
        elif bumptex:
            self.link(bumptex.outputs[0], top.inputs["Height"])
            self.material.addGeoBump(bumptex, top.inputs["Distance"])
            self._link_bump_normal(top)

        top.inputs["Bump"].default_value = bump * Settings.bumpFactor
        self.__mix_with_active(weight, weighttex, top)

        if fresnel:
            self.link_scalar(roughtex, fresnel, roughness, "Roughness")
            self._link_bump_normal(fresnel)
            self.link(fresnel.outputs[0], top.inputs["Fac"])

    # 2
    def _check_translucency(self):
        if not self.is_enabled("Translucency"):
            return False
        if (self.material.thinWall or
            self.volume or
                self.material.translucent):
            return True
        if (self.material.refractive or
                not self.material.translucent):
            return False
    # 1

    def _build_translucency(self):
        if (Settings.materialMethod != 'BSDF' or
                not self._check_translucency()):
            return
        fac = self.getValue("getChannelTranslucencyWeight", 0)
        effect = self.getValue(["Base Color Effect"], 0)
        if fac == 0 and effect != 1:
            return
        self.column += 1
        mat = self.material.rna
        color, tex = self._get_translucent_color()

        if ColorStatic.isBlack(color):
            return

        from daz_import.Elements.ShaderGroup import TranslucentShaderGroup

        node = self.add_group(TranslucentShaderGroup,
                              "DAZ Translucent", size=200)
        node.width = 200
        self.link_color(tex, node, color, "Color")
        node.inputs["Gamma"].default_value = 3.5
        node.inputs["Scale"].default_value = 1.0
        ssscolor, ssstex, sssmode = self.getSSSColor()
        radius, radtex = self.getSSSRadius(color, ssscolor, ssstex, sssmode)
        self.link_color(radtex, node, radius, "Radius")
        node.inputs["Cycles Mix Factor"].default_value = (
            not Settings.useVolume)
        node.inputs["Eevee Mix Factor"].default_value = 1.0
        self._link_bump_normal(node)

        fac, factex = self._get_color_tex(
            "getChannelTranslucencyWeight", "NONE", 0)
        if effect == 1:  # Scatter and transmit
            fac = 0.5 + fac/2
            if factex and factex.type == 'MATH':
                factex.inputs[0].default_value = fac
        self.__mix_with_active(fac, factex, node)
        Settings.usedFeatures_["Transparent"] = True
        self.endSSS()

    # 2
    def _get_translucent_color(self):
        color, tex = self._get_color_tex(
            ["Translucency Color"], "COLOR", ColorStatic.BLACK)
        if (tex is None and
                (Settings.useFakeTranslucencyTexture or not Settings.useVolume)):
            tex = self._diffuse_tex
        return color, tex

    def getSSSColor(self):
        sssmode = self.getValue(["SSS Mode"], 0)
        # [ "Mono", "Chromatic" ]

        if sssmode == 1:
            color, tex = self._get_color_tex(
                "getChannelSSSColor", "COLOR", ColorStatic.BLACK)
        elif sssmode == 0:
            sss, tex = self._get_color_tex(["SSS Amount"], "NONE", 0.0)
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
            s, ssstex = self._get_color_tex("getChannelSSSAmount", "NONE", 0)
            if s > 1:
                s = 1
            ssscolor = Vector((s, s, s))
        trans, transtex = self._get_color_tex(
            ["Transmitted Color"], "COLOR", ColorStatic.BLACK)
        if ColorStatic.isWhite(trans):
            trans = ColorStatic.BLACK

        rad, radtex = self.sumColors(ssscolor, ssstex, trans, transtex)
        radius = rad * 2.0 * Settings.scale_
        return radius, radtex
    
    # Node
    def sumColors(self, color, tex, color2, tex2):
        if tex and tex2:
            tex = self._mix_texs('ADD', tex, tex2)
        elif tex2:
            tex = tex2
        color = Vector(color) + Vector(color2)
        return color, tex
    
    # # Node
    # def multiplyColors(self, color, tex, color2, tex2):
    #     if tex and tex2:
    #         tex = self._mix_texs('MULTIPLY', tex, tex2)
    #     elif tex2:
    #         tex = tex2
    #     color = self._comp_prod(color, color2)
    #     return color, tex
    
    # MaterialData
    def _get_refraction_color(self):
        if self.material.shareGlossy:
            color, tex = self._get_color_tex(
                "getChannelGlossyColor", "COLOR", ColorStatic.WHITE)
            roughness, roughtex = self._get_color_tex(
                "getChannelGlossyRoughness", "NONE", 0, False, maxval=1)
        else:
            color, tex = self._get_color_tex(
                "getChannelRefractionColor", "COLOR", ColorStatic.WHITE)
            roughness, roughtex = self._get_color_tex(
                ["Refraction Roughness"], "NONE", 0, False, maxval=1)
        return color, tex, roughness, roughtex

    # def addInput(self, node, channel, slot, colorSpace, default, maxval=0):
    #     value, tex = self._get_color_tex(
    #         channel, colorSpace, default, maxval=maxval)
        
    #     if VectorStatic.is_vector(default):
    #         node.inputs[slot].default_value[0:3] = value
    #     else:
    #         node.inputs[slot].default_value = value
        
    #     if tex:
    #         self.link(tex.outputs[0], node.inputs[slot])

    #     return value, tex
    
    # Node
    def _set_roughness(self, node, slot, roughness, roughtex, square=True):
        node.inputs[slot].default_value = roughness        
        if not roughtex:
            return roughness

        tex = self.multiplyScalarTex(roughness, roughtex)
        
        if not tex:
            return roughness

        self.link(tex.outputs[0], node.inputs[slot])

        return roughness
    
    # ShaderGraph
    def _build_refraction(self):
        from daz_import.Elements.ShaderGroup import FakeCausticsShaderGroup

        weight, wttex = self._get_color_tex(
            "getChannelRefractionWeight", "NONE", 0.0)
        
        if weight == 0:
            return

        node, color = self._get_refraction_node()
        self.__mix_with_active(weight, wttex, node)

        if not(Settings.useFakeCaustics and not self.material.thinWall):
            return
        
        self.column += 1

        node = self.add_group(FakeCausticsShaderGroup, "DAZ Fake Caustics", args=[
            color], force=True)

        self.__mix_with_active(weight, wttex, node, keep=True)
    
    # Node
    def _get_refraction_node(self):
        from daz_import.Elements.ShaderGroup import RefractionShaderGroup
        self.column += 1
        
        node = self.add_group(RefractionShaderGroup,
                              "DAZ Refraction", size=150)
        node.width = 240

        color, tex = self._get_color_tex(
            "getChannelGlossyColor", "COLOR", ColorStatic.WHITE)
        
        roughness, roughtex = self._get_color_tex(
            "getChannelGlossyRoughness", "NONE", 0, False, maxval=1)
        roughness = roughness**2

        self.link_color(tex, node, color, "Glossy Color")
        self.link_scalar(roughtex, node, roughness, "Glossy Roughness")

        color, coltex, roughness, roughtex = self._get_refraction_color()
        ior, iortex = self._get_color_tex("getChannelIOR", "NONE", 1.45)
        
        roughness = roughness**2

        self.link_color(coltex, node, color, "Refraction Color")
        self.link_scalar(iortex, node, ior, "Fresnel IOR")
        
        if self.material.thinWall:
            node.inputs["Thin Wall"].default_value = 1
            node.inputs["Refraction IOR"].default_value = 1.0
            node.inputs["Refraction Roughness"].default_value = 0.0
            self.material.setTransSettings(False, True, color, 0.1)
        else:
            node.inputs["Thin Wall"].default_value = 0
            self.link_scalar(roughtex, node, roughness, "Refraction Roughness")
            self.link_scalar(iortex, node, ior, "Refraction IOR")
            self.material.setTransSettings(True, False, color, 0.2)
        
        self._link_bump_normal(node)
        return node, color
    
    # ShaderGraph
    def _build_cutout(self):
        from daz_import.Elements.ShaderGroup import TransparentShaderGroup

        alpha, tex = self._get_color_tex(
            "getChannelCutoutOpacity", "NONE", 1.0)
        
        if not(alpha < 1 or tex):
            return

        self.column += 1
        self.useCutout = True

        if alpha == 0:
            node = self.add_node("ShaderNodeBsdfTransparent")
            self.cycles = node
            self.eevee = node
            tex = None
        else:            
            node = self.add_group(
                TransparentShaderGroup, "DAZ Transparent")
            self.__mix_with_active(alpha, tex, node)

        node.inputs["Color"].default_value[0:3] = ColorStatic.WHITE
        
        if alpha < 1 or tex:
            self.material.setTransSettings(
                False, False, ColorStatic.WHITE, alpha)

        Settings.usedFeatures_["Transparent"] = True

    
    # Any
    def _build_emission(self):
        from daz_import.Elements.ShaderGroup import EmissionShaderGroup

        if not Settings.useEmission:
            return

        color = self.get_color("getChannelEmissionColor", ColorStatic.BLACK)

        if ColorStatic.isBlack(color):
            return

        self.column += 1
        emit = self.add_group(EmissionShaderGroup, "DAZ Emission")
        self._add_emit_color(emit, "Color")

        strength = self._get_luminance(emit)

        emit.inputs["Strength"].default_value = strength
        self.link(self.cycles_socket(), emit.inputs["Cycles"])
        self.link(self.eevee_socket(), emit.inputs["Eevee"])
        self.cycles = self.eevee = emit
        self._set_one_sided()

    # Node
    def _add_emit_color(self, emit_node, slot):
        color, tex = self._get_color_tex(
            "getChannelEmissionColor", "COLOR", ColorStatic.BLACK)
        if tex is None:
            _, tex = self._get_color_tex(
                ["Luminance"], "COLOR", ColorStatic.BLACK)
        temp = self.getValue(["Emission Temperature"], None)

        if temp is None:
            self.link_color(tex, emit_node, color, slot)
            return
        elif temp == 0:
            temp = 6500

        blackbody = self.add_node("ShaderNodeBlackbody", self.column-2)
        blackbody.inputs["Temperature"].default_value = temp

        if ColorStatic.isWhite(color) and tex is None:
            self.link(blackbody.outputs["Color"], emit_node.inputs[slot])
        else:
            mult = self.add_node("ShaderNodeMixRGB", self.column-1)
            mult.blend_type = 'MULTIPLY'
            mult.inputs[0].default_value = 1

            self.link(blackbody.outputs["Color"], mult.inputs[1])
            self.link_color(tex, mult, color, 2)
            self.link(mult.outputs[0], emit_node.inputs[slot])

    # Node / Material
    def _get_luminance(self, emit: ShaderNode):
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

    # Node 
    def _set_one_sided(self):
        from daz_import.Elements.ShaderGroup import OneSidedShaderGroup

        twosided = self.getValue(["Two Sided Light"], False)
        if twosided:
            return
        
        node = self.add_group(OneSidedShaderGroup,
                                "DAZ VectorStatic.one-Sided")
        self.link(self.cycles_socket(), node.inputs["Cycles"])
        self.link(self.eevee_socket(), node.inputs["Eevee"])

        self.cycles = self.eevee = node

   
    # Node
    def _invert_color(self, color, tex, col):
        inverse = (1-color[0], 1-color[1], 1-color[2])
        return inverse, self._invert_tex(tex, col)
    
    # Shader
    def _build_volume(self):
        if (self.material.thinWall or
            Settings.materialMethod != "BSDF" or
                not Settings.useVolume):
            return
        self.volume = None

        if self.is_enabled("Translucency"):
            transcolor, transtex = self._get_color_tex(
                ["Transmitted Color"], "COLOR", ColorStatic.BLACK)

            sssmode, ssscolor, ssstex = self._get_SSS_data(transcolor)
            
            if self.is_enabled("Transmission"):
                self._build_volume_transmission(transcolor, transtex)
            
            if self.is_enabled("Subsurface"):
                self._build_volume_sub_surface(sssmode, ssscolor, ssstex)

        if self.volume:
            self.volume.width = 240
            Settings.usedFeatures_["Volume"] = True
    
    # MaterialData
    def _get_SSS_data(self, _):                
        if self.material.shader_key == 'UBER_IRAY':
            sssmode = self.getValue(["SSS Mode"], 0)
        elif self.material.shader_key == 'PBRSKIN':
            sssmode = 1
        else:
            sssmode = 0

        # [ "Mono", "Chromatic" ]

        if sssmode == 1:
            ssscolor, ssstex = self._get_color_tex(
                "getChannelSSSColor", "COLOR", ColorStatic.BLACK)
            return 1, ssscolor, ssstex
        else:
            return 0, ColorStatic.WHITE, None
    
    # Node
    def _build_volume_transmission(self, transcolor, transtex):
        from daz_import.Elements.ShaderGroup import VolumeShaderGroup

        dist = self.getValue(["Transmitted Measurement Distance"], 0.0)

        if ColorStatic.isBlack(transcolor) or ColorStatic.isWhite(transcolor) or dist == 0.0:
            return

        self.volume = self.add_group(VolumeShaderGroup, "DAZ Volume")
        self.volume.inputs["Absorbtion Density"].default_value = 100/dist
        self.link_color(transtex, self.volume,
                        transcolor, "Absorbtion Color")
    
    # MaterilData / Node
    def _build_volume_sub_surface(self, sssmode, ssscolor, ssstex):
        from daz_import.Elements.ShaderGroup import VolumeShaderGroup
        
        if self.material.shader_key == 'UBER_IRAY':
            factor = 50
        else:
            factor = 25

        sss = self.getValue(["SSS Amount"], 0.0)
        dist = self.getValue("getChannelScatterDist", 0.0)

        if not (sssmode == 0 or ColorStatic.isBlack(ssscolor) or ColorStatic.isWhite(ssscolor) or dist == 0.0):
            color, tex = self._invert_color(ssscolor, ssstex, 6)
            if self.volume is None:
                self.volume = self.add_group(VolumeShaderGroup, "DAZ Volume")
            self.link_color(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = factor/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue([
                                                                                   "SSS Direction"], 0)
        elif sss > 0 and dist > 0.0:
            if self.volume is None:
                self.volume = self.add_group(VolumeShaderGroup, "DAZ Volume")
            sss, tex = self._get_color_tex(["SSS Amount"], "NONE", 0.0)
            color = (sss, sss, sss)
            self.link_color(tex, self.volume, color, "Scatter Color")
            self.volume.inputs["Scatter Density"].default_value = factor/dist
            self.volume.inputs["Scatter Anisotropy"].default_value = self.getValue([
                                                                                   "SSS Direction"], 0)
    # Node
    def _build_output(self):
        self.column += 1
        output = self.add_node("ShaderNodeOutputMaterial")
        output.target = 'ALL'

        if self.cycles:
            self.link(self.cycles_socket(), output.inputs["Surface"])

        if self.volume and not self.useCutout:
            self.link(self.volume.outputs[0], output.inputs["Volume"])

        if self.displacement:
            self.link(self.displacement, output.inputs["Displacement"])

        if self.liegroups:
            node = self.add_node("ShaderNodeValue", col=self.column-1)
            node.outputs[0].default_value = 1.0
            
            for lie in self.liegroups:
                self.link(node.outputs[0], lie.inputs["Alpha"])

        if self.volume or self.eevee:
            output.target = 'CYCLES'
            outputEevee = self.add_node("ShaderNodeOutputMaterial")
            outputEevee.target = 'EEVEE'
            
            if self.eevee:
                self.link(self.eevee_socket(),
                          outputEevee.inputs["Surface"])
            elif self.cycles:
                self.link(self.cycles_socket(),
                          outputEevee.inputs["Surface"])

            if self.displacement:
                self.link(self.displacement,
                          outputEevee.inputs["Displacement"])
    
    # Node
    def _build_displacement_nodes(self):
        channel = self.material.getChannelDisplacement()

        if not(channel and
                self.is_enabled("Displacement") and
                Settings.useDisplacement):
            return

        tex = self._get_tex_image_node(channel, "NONE")
        if not tex:
            return

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
        node = self.add_group(DisplacementShaderGroup, "DAZ Displacement")
        self.link(tex.outputs[0], node.inputs["Texture"])

        node.inputs["Strength"].default_value = strength
        node.inputs["Max"].default_value = Settings.scale_ * dmax
        node.inputs["Min"].default_value = Settings.scale_ * dmin

        self._link_normal(node)
        self.displacement = node.outputs["Displacement"]

        mat = self.material.rna
        mat.cycles.displacement_method = 'BOTH'
    
    # Node
    def _add_single_texture(self, col, asset, map, colorSpace):
        isnew = False

        img = asset.buildCycles(colorSpace)

        if img:
            imgname = img.name
        else:
            imgname = asset.getName()

        hasMap = asset.hasMapping(map)
        texnode = self._get_tex_node_(imgname, colorSpace)

        if not hasMap and texnode:
            return texnode, False

        texnode = self._add_texture_node(col, img, imgname, colorSpace)
        isnew = True

        if not hasMap:
            self._set_tex_node__(imgname, texnode, colorSpace)

        return texnode, isnew
    
    # Node
    def _add_texture_node(self, col, img, imgname, colorSpace) -> ShaderNodeTexImage:
        node = self.add_node("ShaderNodeTexImage", col)

        node.image = img
        node.interpolation = Settings.imageInterpolation
        node.label = imgname.rsplit("/", 1)[-1]

        self._set_color_space(node, colorSpace)
        node.name = imgname

        if hasattr(node, "image_user"):
            node.image_user.frame_duration = 1
            node.image_user.frame_current = 1

        return node
    
    # Node
    @staticmethod
    def _set_color_space(node, colorSpace):
        if hasattr(node, "color_space"):
            node.color_space = colorSpace

    # Node
    def add_image_tex_node(self, filepath: str, tname, col) -> ShaderNodeTexImage:
        img = bpy.data.images.load(filepath)
        img.name = os.path.splitext(os.path.basename(filepath))[0]
        img.colorspace_settings.name = "Non-Color"

        return self._add_texture_node(col, img, tname, "NONE")

    # ShaderNodeGroup
    def _get_tex_node_(self, key, colorSpace):
        list_ = self.texnodes.get(key, [])

        for texnode, colorSpace1 in list_:
            if colorSpace1 == colorSpace:
                return texnode

        return None

    # ShaderNodeGroup
    def _set_tex_node__(self, key, texnode, colorSpace):
        if key not in self.texnodes.keys():
            self.texnodes[key] = []

        self.texnodes[key].append((texnode, colorSpace))
    
    # Node
    def _link_vector(self, texco, node, slot="Vector"):
        if not texco:
            return

        if (isinstance(texco, bpy.types.NodeSocketVector) or
                isinstance(texco, bpy.types.NodeSocketFloat)):
            self.link(texco, node.inputs[slot])
            return

        if "Vector" in texco.outputs.keys():
            self.link(texco.outputs["Vector"], node.inputs[slot])
        else:
            self.link(texco.outputs["UV"], node.inputs[slot])

    # ShaderGraph / Node
    def _get_tex_image_node(self, channel, colorSpace=None):
        col = self.column-2
        textures, maps = self.material.getTextures(channel)

        if len(textures) != len(maps):
            print(textures, '\n', maps)
            raise DazError("Bug: Num assets != num maps")
        elif len(textures) == 0:
            return None
        elif len(textures) == 1:
            texnode, isnew = self._add_single_texture(
                col, textures[0], maps[0], colorSpace)
            if isnew:
                self._link_vector(self.texco, texnode)
            return texnode

        from daz_import.Elements.ShaderGroup import LieShaderGroup

        node = self.add_node("ShaderNodeGroup", col)
        node.width = 240

        try:
            name = os.path.basename(textures[0].map.url)
        except:
            name = "Group"

        group = LieShaderGroup()
        group.create(node, name, self)
        self._link_vector(self.texco, node)
        group.addTextureNodes(textures, maps, colorSpace)

        node.inputs["Alpha"].default_value = 1
        self.liegroups.append(node)

        return node
    
    # Node
    def _mix_texs(self, op, tex1, tex2, slot1=0, slot2=0, color1=None, color2=None, fac=1, factex=None):

        if fac < 1 or factex:
            pass
        elif tex1 is None:
            return tex2
        elif tex2 is None:
            return tex1

        mix = self.add_node("ShaderNodeMixRGB", self.column-1)
        mix.blend_type = op
        mix.use_alpha = False
        mix.inputs[0].default_value = fac

        if factex:
            self.link(factex.outputs[0], mix.inputs[0])

        if color1:
            mix.inputs[1].default_value[0:3] = color1

        if tex1:
            self.link(tex1.outputs[slot1], mix.inputs[1])

        if color2:
            mix.inputs[2].default_value[0:3] = color2

        if tex2:
            self.link(tex2.outputs[slot2], mix.inputs[2])

        return mix

    # ShaderGraph
    def __mix_with_active(self, fac, tex, shader, useAlpha=False, keep=False):
        if shader.type != 'GROUP':
            raise RuntimeError("BUG: __mix_with_active", shader.type)

        if fac == 0 and tex is None and not keep:
            return
        elif fac == 1 and tex is None and not keep:
            shader.inputs["Fac"].default_value = fac
            self.cycles = shader
            self.eevee = shader
            return

        if self.eevee:
            self.__make_active_mix(
                "Eevee", self.eevee, self.eevee_socket(), fac, tex, shader, useAlpha)
        self.eevee = shader

        if self.cycles:
            self.__make_active_mix(
                "Cycles", self.cycles, self.cycles_socket(), fac, tex, shader, useAlpha)

        self.cycles = shader
    
    # Node
    def __make_active_mix(self, slot, active, socket, fac, tex, shader, useAlpha):
        self.link(socket, shader.inputs[slot])
        shader.inputs["Fac"].default_value = fac

        if not tex:
            return

        if useAlpha and "Alpha" in tex.outputs.keys():
            texsocket = tex.outputs["Alpha"]
        else:
            texsocket = tex.outputs[0]

        self.link(texsocket, shader.inputs["Fac"])

    # Node
    def link_color(self, tex, node, color, slot=0):
        node.inputs[slot].default_value[0:3] = color

        if tex:
            tex = self._multiply_vector_tex(color, tex)
            if tex:
                self.link(tex.outputs[0], node.inputs[slot])

        return tex

    # NODE
    def link_scalar(self, tex, node, value, slot):
        node.inputs[slot].default_value = value
        if tex:
            tex = self.multiplyScalarTex(value, tex)
            if tex:
                self.link(tex.outputs[0], node.inputs[slot])
        return tex

    # NODE
    def add_slot(self, channel, node, slot, value, value0, invert):
        node.inputs[slot].default_value = value

        tex = self._get_tex_image_node(channel, "NONE")
        
        if not tex:
            return tex
        
        tex = self._fix_tex(tex, value0, invert)
        
        if not tex:
            return tex

        self.link(tex.outputs[0], node.inputs[slot])

        return tex

    def _fix_tex(self, tex, value, invert):
        _, tex = self.multiplySomeTex(value, tex)
        if invert:
            return self._invert_tex(tex, 3)
        else:
            return tex
    # Node
    def _invert_tex(self, tex, col):
        if tex:
            inv = self.add_node("ShaderNodeInvert", col)
            self.link(tex.outputs[0], inv.inputs["Color"])
            return inv
        else:
            return None

    def multiplySomeTex(self, value, tex, slot=0):
        if isinstance(value, float) or isinstance(value, int):
            if tex and value != 1:
                tex = self.multiplyScalarTex(value, tex, slot)
        elif tex:
            tex = self._multiply_vector_tex(value, tex, slot)
        return value, tex

    def _multiply_vector_tex(self, color, tex, slot=0, col=None) -> ShaderNodeMixRGB:
        if ColorStatic.isWhite(color):
            return tex
        elif ColorStatic.isBlack(color):
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex
        if col is None:
            col = self.column-1

        mix = self.add_node("ShaderNodeMixRGB", col)

        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value[0:3] = color

        self.link(tex.outputs[0], mix.inputs[2])
        return mix
    
    # Node
    def multiplyScalarTex(self, value, tex, slot=0, col=None):
        if value == 1:
            return tex
        elif value == 0:
            return None
        elif (tex and tex.type not in ['TEX_IMAGE', 'GROUP']):
            return tex

        if col is None:
            col = self.column-1

        mult = self.add_node("ShaderNodeMath", col)
        mult.operation = 'MULTIPLY'
        mult.inputs[0].default_value = value
        self.link(tex.outputs[slot], mult.inputs[1])

        return mult

    def multiplyAddScalarTex(self, factor, term, tex, slot=0, col=None):
        if col is None:
            col = self.column-1
        mult = self.add_node("ShaderNodeMath", col)
        try:
            mult.operation = 'MULTIPLY_ADD'
            ok = True
        except TypeError:
            ok = False
        if ok:
            self.link(tex.outputs[slot], mult.inputs[0])
            mult.inputs[1].default_value = factor
            mult.inputs[2].default_value = term
            return mult
        else:
            mult.operation = 'MULTIPLY'
            self.link(tex.outputs[slot], mult.inputs[0])
            mult.inputs[1].default_value = factor
            add = self.add_node("ShaderNodeMath", col)
            add.operation = 'ADD'
            add.inputs[1].default_value = term
            self.link(mult.outputs[slot], add.inputs[0])
            return add

    def multiplyTexs(self, tex1, tex2):
        if tex1 and tex2:
            mult = self.add_node("ShaderNodeMath")
            mult.operation = 'MULTIPLY'
            self.link(tex1.outputs[0], mult.inputs[0])
            self.link(tex2.outputs[0], mult.inputs[1])
            return mult
        elif tex1:
            return tex1
        else:
            return tex2

    def selectDiffuse(self, marked):
        if self._diffuse_tex and marked[self._diffuse_tex.name]:
            self._diffuse_tex.select = True
            self.shader_graph.set_active_node(self._diffuse_tex)

    # 1 ShaderNode
    def _get_link(self, node, key_slot):
        for link in self.shader_graph.links:
            if link.to_node == node and \
                    link.to_socket.name == key_slot:
                return link
        return None

    # 9 ShaderNode
    def _remove_link(self, node, slot):
        if link := self._get_link(node, slot):
            self.shader_graph.links.remove(link)

    # 10 ShaderNode
    def _replace_slot(self, node, slot, value):
        node.inputs[slot].default_value = value
        self._remove_link(node, slot)

    # 2 ShaderGraph
    def find_texco(self, col):
        if nodes := self.find_nodes("TEX_COORD"):
            return nodes[0]
        else:
            return self.add_node("ShaderNodeTexCoord", col)

    # 3  to shader_graph
    def find_nodes(self, nodeType):
        nodes = []
        for node in self.shader_graph.nodes.values():
            if node.type == nodeType:
                nodes.append(node)
        return nodes

    def findNode(self, key):
        return super().findNode(self.shader_graph, key)

    def set_material(self, mat: BlenderMaterial):
        mat.use_nodes = True
        self.shader_graph.init(mat)
        # self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links

    def set_material_object(self, obj):
        self.shader_graph.init(obj, False)
        # self.nodes = obj.nodes
        self.links = obj.links

    def pruneNodeTree(self):
        return super().pruneNodeTree(self.shader_graph)
