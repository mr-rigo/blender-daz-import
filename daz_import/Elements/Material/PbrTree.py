# import bpy
# import math
from mathutils import Vector
from daz_import.Elements.Color import ColorStatic
from daz_import.Lib.Settings import Settings
from daz_import.Lib.Errors import *
from daz_import.utils import *
from daz_import.Elements.Material.Cycles import CyclesShader


class PBRShader(CyclesShader):
    def __init__(self, *args):
        super().__init__(*args)
        self.pbr = None
        self.type = 'PBR'

    def __repr__(self):
        return ("<Pbr %s %s %s>" % (self.material.rna, self.shader_graph.nodes, self.links))

    def _build_layer(self, uvname):
        self.column = 4
        
        try:
            self.pbr = self.add_node("ShaderNodeBsdfPrincipled")
            self.ycoords[self.column] -= 500
        except RuntimeError:
            self.pbr = None
            self.type = 'CYCLES'
            
        if self.pbr is None:
            return super()._build_layer(uvname)

        self.cycles = self.eevee = self.pbr
        self._build_normal(uvname)
        self._build_bump()
        self._build_detail(uvname)
        self.buildPBRNode()
        self.linkPBRNormal(self.pbr)
        self.postPBR = False

        if self._build_makeup():
            self.postPBR = True

        if self._build_overlay():
            self.postPBR = True

        if self.material.dualLobeWeight > 0:
            self._build_dual_lobe()
            self._replace_slot(self.pbr, "Specular", 0)
            self.postPBR = True

        if self.material.refractive:

            if Settings.refractiveMethod == 'BSDF':
                self.buildRefraction()
                self.postPBR = True
            else:
                self.buildPBRRefraction()
        else:
            self.buildEmission()

    def linkPBRNormal(self, pbr):
        if self.bump:
            self.link(self.bump.outputs["Normal"], pbr.inputs["Normal"])
            self.link(
                self.bump.outputs["Normal"], pbr.inputs["Clearcoat Normal"])

        elif self.normal:
            self.link(self.normal.outputs["Normal"], pbr.inputs["Normal"])
            self.link(
                self.normal.outputs["Normal"], pbr.inputs["Clearcoat Normal"])

    def buildCutout(self):
        if "Alpha" in self.pbr.inputs.keys() and not self.postPBR:
            alpha, tex = self._get_color_tex("getChannelCutoutOpacity", "NONE", 1)
            if alpha < 1 or tex:
                self.material.setTransSettings(
                    False, False, ColorStatic.WHITE, alpha)
                self.useCutout = True
            self.pbr.inputs["Alpha"].default_value = alpha
            if tex:
                self.link(tex.outputs[0], self.pbr.inputs["Alpha"])
        else:
            CyclesShader.buildCutout(self)

    def buildVolume(self):
        ...

    def buildEmission(self):
        if not Settings.useEmission:
            return
        elif "Emission" in self.pbr.inputs.keys():
            color = self.get_color("getChannelEmissionColor", ColorStatic.BLACK)
            if not ColorStatic.isBlack(color):
                self.addEmitColor(self.pbr, "Emission")
        else:
            CyclesShader.buildEmission(self)
            self.postPBR = True

    def buildPBRNode(self):
        if self.is_enabled("Diffuse"):
            color, tex = self._get_diffuse_color()
            self.diffuseColor = color
            self.diffuseTex = tex
            self.link_color(tex, self.pbr, color, "Base Color")
        else:
            self.diffuseColor = ColorStatic.WHITE
            self.diffuseTex = None

        # Metallic Weight
        if self.is_enabled("Metallicity"):
            metallicity, tex = self._get_color_tex(
                ["Metallic Weight"], "NONE", 0.0)
            self.link_scalar(tex, self.pbr, metallicity, "Metallic")
        else:
            metallicity = 0

        useTex = not (self.material.basemix == 0 and metallicity > 0.5)

        # Subsurface scattering
        self.buildSSS()

        # Anisotropic
        anisotropy, tex = self._get_color_tex(["Glossy Anisotropy"], "NONE", 0)
        if anisotropy > 0:
            self.link_scalar(tex, self.pbr, anisotropy, "Anisotropic")
            anirot, tex = self._get_color_tex(
                ["Glossy Anisotropy Rotations"], "NONE", 0)
            value = 0.75 - anirot
            self.link_scalar(tex, self.pbr, value, "Anisotropic Rotation")

        # Roughness
        channel, invert, value, roughness = self.getGlossyRoughness()
        roughness *= (1 + anisotropy)
        self.add_slot(channel, self.pbr, "Roughness", roughness, value, invert)

        # Specular
        strength, strtex = self._get_color_tex(
            "getChannelGlossyLayeredWeight", "NONE", 1.0, False)
        if self.material.shader_key == 'UBER_IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                # principled specular = iray glossy reflectivity * iray glossy layered weight * iray glossy color / 0.8
                refl, reftex = self._get_color_tex(
                    "getChannelGlossyReflectivity", "NONE", 0.5, False, useTex)
                color, coltex = self._get_color_tex(
                    "getChannelGlossyColor", "COLOR", ColorStatic.WHITE, True, useTex)
                if reftex and coltex:
                    reftex = self.mixTexs('MULTIPLY', coltex, reftex)
                elif coltex:
                    reftex = coltex
                tex = self.mixTexs('MULTIPLY', strtex, reftex)
                factor = 1.25 * refl * strength
                value = factor * VectorStatic.color(color)
            elif self.material.basemix == 1:  # Specular/Glossiness
                # principled specular = iray glossy specular * iray glossy layered weight * 16
                color, reftex = self._get_color_tex(
                    "getChannelGlossySpecular", "COLOR", ColorStatic.WHITE, True, useTex)
                tex = self.mixTexs('MULTIPLY', strtex, reftex)
                factor = 16 * strength
                value = factor * VectorStatic.color(color)
        else:
            color, coltex = self._get_color_tex(
                "getChannelGlossyColor", "COLOR", ColorStatic.WHITE, True, useTex)
            tex = self.mixTexs('MULTIPLY', strtex, coltex)
            value = factor = strength * VectorStatic.color(color)

        self.pbr.inputs["Specular"].default_value = UtilityStatic.clamp(value)
        if tex and useTex:
            tex = self.multiplyScalarTex(UtilityStatic.clamp(factor), tex)
            if tex:
                self.link(tex.outputs[0], self.pbr.inputs["Specular"])

        # Clearcoat
        top, toptex = self._get_color_tex(["Top Coat Weight"], "NONE", 1.0, False)

        if self.material.shader_key == 'UBER_IRAY':
            if self.material.basemix == 0:    # Metallic/Roughness
                refl, reftex = self._get_color_tex(
                    "getChannelGlossyReflectivity", "NONE", 0.5, False, useTex)
                tex = self.mixTexs('MULTIPLY', toptex, reftex)
                value = 1.25 * refl * top
            else:
                tex = toptex
                value = top
        else:
            tex = toptex
            value = top

        self.pbr.inputs["Clearcoat"].default_value = UtilityStatic.clamp(value)

        if tex and useTex:
            tex = self.multiplyScalarTex(UtilityStatic.clamp(value), tex)
            if tex:
                self.link(tex.outputs[0], self.pbr.inputs["Clearcoat"])

        rough, tex = self._get_color_tex(["Top Coat Roughness"], "NONE", 1.45)
        self.link_scalar(tex, self.pbr, rough, "Clearcoat Roughness")

        # Sheen
        if self.is_enabled("Velvet"):
            velvet, tex = self._get_color_tex(["Velvet Strength"], "NONE", 0.0)
            self.link_scalar(tex, self.pbr, velvet, "Sheen")

    def buildSSS(self):
        if not self.is_enabled("Subsurface"):
            return
        if not self.checkTranslucency():
            return
        wt, wttex = self._get_color_tex("getChannelTranslucencyWeight", "NONE", 0)
        if wt == 0:
            return
        color, coltex = self.getTranslucentColor()

        if ColorStatic.isBlack(color):
            return

        # a 3.5 gamma for the translucency texture is used to avoid the "white skin" effect
        gamma = self.add_node("ShaderNodeGamma", col=3)
        gamma.inputs["Gamma"].default_value = 3.5

        ssscolor, ssstex, sssmode = self.getSSSColor()
        radius, radtex = self.getSSSRadius(color, ssscolor, ssstex, sssmode)
        self.link_color(coltex, gamma, color, "Color")
        self.pbr.subsurface_method = Settings.sssMethod
        self.link(gamma.outputs[0], self.pbr.inputs["Subsurface Color"])
        self.link_scalar(wttex, self.pbr, wt, "Subsurface")
        self.link_color(radtex, self.pbr, radius, "Subsurface Radius")
        self.endSSS()

    def getRefractionWeight(self):
        channel = self.material.getChannelRefractionWeight()

        if channel:
            return self._get_color_tex("getChannelRefractionWeight", "NONE", 0.0)
        channel = self.material.getChannelOpacity()

        if channel:
            value, tex = self._get_color_tex("getChannelOpacity", "NONE", 1.0)
            invtex = self._fix_tex(tex, value, True)
            return 1-value, invtex

        return 1, None

    def buildPBRRefraction(self):
        weight, wttex = self._get_color_tex(
            "getChannelRefractionWeight", "NONE", 0.0)

        if weight == 0:
            return

        color, coltex, roughness, roughtex = self.getRefractionColor()

        ior, iortex = self._get_color_tex("getChannelIOR", "NONE", 1.45)

        if Settings.refractiveMethod == 'SECOND':
            if weight < 1 or wttex:
                self.column += 1
                pbr = pbr2 = self.add_node("ShaderNodeBsdfPrincipled")
                self.ycoords[self.column] -= 500
                self.linkPBRNormal(pbr2)
                pbr2.inputs["Transmission"].default_value = 1.0
            else:
                pbr = self.pbr
                pbr2 = None
                self._replace_slot(pbr, "Transmission", weight)

            if self.material.thinWall:
                from daz_import.Elements.ShaderGroup import RayClipShaderGroup
                self.column += 1
                clip = self.add_group(RayClipShaderGroup, "DAZ Ray Clip")
                self.link(pbr.outputs[0], clip.inputs["Shader"])
                self.link_color(coltex, clip, color, "Color")
                self.cycles = self.eevee = clip
            else:
                clip = pbr

            if pbr2:
                self.column += 1
                mix = self.mixShaders(weight, wttex, self.pbr, clip)
                self.cycles = self.eevee = mix
            self.postPBR = True
        else:
            pbr = self.pbr
            self._replace_slot(pbr, "Transmission", weight)

        if self.material.thinWall:
            # if thin walled is on then there's no volume
            # and we use the clearcoat channel for reflections
            #  principled ior = 1
            #  principled roughness = 0
            #  principled clearcoat = (iray refraction index - 1) * 10 * iray glossy layered weight
            #  principled clearcoat roughness = 0
            self.material.setTransSettings(True, False, color, 0.1)
            self._replace_slot(pbr, "IOR", 1.0)
            self._replace_slot(pbr, "Roughness", 0.0)
            strength, strtex = self._get_color_tex(
                "getChannelGlossyLayeredWeight", "NONE", 1.0, False)
            clearcoat = (ior-1)*10*strength
            self._remove_link(pbr, "Clearcoat")
            self.link_scalar(strtex, pbr, clearcoat, "Clearcoat")
            self._replace_slot(pbr, "Clearcoat Roughness", 0)

        else:
            # principled transmission = 1
            # principled metallic = 0
            # principled specular = 0.5
            # principled ior = iray refraction index
            # principled roughness = iray glossy roughness
            self.material.setTransSettings(True, False, color, 0.2)
            transcolor, transtex = self._get_color_tex(
                ["Transmitted Color"], "COLOR", ColorStatic.BLACK)
            dist = self.getValue(["Transmitted Measurement Distance"], 0.0)
            if not (ColorStatic.isBlack(transcolor) or ColorStatic.isWhite(transcolor) or dist == 0.0):
                coltex = self.mixTexs('MULTIPLY', coltex, transtex)
                color = self._comp_prod(color, transcolor)
            self._replace_slot(pbr, "Metallic", 0)
            self._replace_slot(pbr, "Specular", 0.5)
            self._remove_link(pbr, "IOR")
            self.link_scalar(iortex, pbr, ior, "IOR")
            self._remove_link(pbr, "Roughness")
            self.setRoughness(pbr, "Roughness", roughness,
                              roughtex, square=False)

        self._remove_link(pbr, "Base Color")
        self.link_color(coltex, pbr, color, "Base Color")
        self._replace_slot(pbr, "Subsurface", 0)
        self._remove_link(pbr, "Subsurface Color")
        pbr.inputs["Subsurface Color"].default_value[0:3] = ColorStatic.WHITE
        if self.material.shareGlossy:
            self._replace_slot(pbr, "Specular Tint", 1.0)

    def mixShaders(self, weight, wttex, node1, node2):
        mix = self.add_node("ShaderNodeMixShader")
        mix.inputs[0].default_value = weight
        if wttex:
            self.link(wttex.outputs[0], mix.inputs[0])
        self.link(node1.outputs[0], mix.inputs[1])
        self.link(node2.outputs[0], mix.inputs[2])
        return mix

    def getGlossyRoughness(self):
        # principled roughness = iray glossy roughness = 1 - iray glossiness
        channel, invert = self.material.getChannelGlossiness()
        invert = not invert

        value = UtilityStatic.clamp(
            self.material.channelsData.getChannelValue(channel, 0.5))

        if invert:
            roughness = 1 - value
        else:
            roughness = value

        return channel, invert, value, roughness

    def setPBRValue(self, slot, value, default, maxval=0):
        if isinstance(default, Vector):
            if isinstance(value, float) or isinstance(value, int):
                value = Vector((value, value, value))
            self.pbr.inputs[slot].default_value[0:3] = value
        else:
            value = VectorStatic.color(value)

            if maxval and value > maxval:
                value = maxval
            self.pbr.inputs[slot].default_value = value
