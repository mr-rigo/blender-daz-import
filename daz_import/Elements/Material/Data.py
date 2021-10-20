from collections import OrderedDict


class Dict(OrderedDict):

    def channel(self, cname):
        data = self[cname]
        if len(data) == 6:
            return data
        else:
            nodeType, slot, ncomps = data

            return (nodeType, slot, None, None, ncomps, None)


TweakableChannels = Dict([
    ("Bump And Normal", None),
    ("Bump Strength", ("BUMP", "Strength", "use_map_normal", "normal_factor", 1, None)),
    ("Bump Distance", ("BUMP", "Distance", 1)),
    ("Normal Strength", ("NORMAL_MAP", "Strength",
                         "use_map_normal", "normal_factor", 1, None)),

    ("Diffuse", None),
    ("Diffuse Color", ("BSDF_DIFFUSE", "Color", 4)),
    ("Diffuse Roughness", ("BSDF_DIFFUSE", "Roughness", 1)),

    ("Glossy", None),
    ("Glossy Color", ("DAZ Glossy", "Color", 4)),
    ("Glossy Roughness", ("DAZ Glossy", "Roughness", 1)),
    ("Glossy Strength", ("DAZ Glossy", "Fac", 1)),

    ("Fresnel", None),
    ("Fresnel IOR", ("DAZ Fresnel", "IOR", 1)),
    ("Fresnel Roughness", ("DAZ Fresnel", "Roughness", 1)),

    ("Dual Lobe Uber", None),
    ("Dual Lobe Uber Weight", ("DAZ Dual Lobe Uber", "Weight", 1)),
    ("Dual Lobe Uber IOR", ("DAZ Dual Lobe Uber", "IOR", 1)),
    ("Dual Lobe Uber Roughness 1", ("DAZ Dual Lobe Uber", "Roughness 1", 1)),
    ("Dual Lobe Uber Roughness 2", ("DAZ Dual Lobe Uber", "Roughness 2", 1)),
    ("Dual Lobe Uber Strength", ("DAZ Dual Lobe Uber", "Fac", 1)),

    ("Dual Lobe PBR", None),
    ("Dual Lobe PBR Weight", ("DAZ Dual Lobe PBR", "Weight", 1)),
    ("Dual Lobe PBR IOR", ("DAZ Dual Lobe PBR", "IOR", 1)),
    ("Dual Lobe PBR Roughness 1", ("DAZ Dual Lobe PBR", "Roughness 1", 1)),
    ("Dual Lobe PBR Roughness 2", ("DAZ Dual Lobe PBR", "Roughness 2", 1)),
    ("Dual Lobe PBR Strength", ("DAZ Dual Lobe PBR", "Fac", 1)),

    ("Translucency", None),
    ("Translucency Color", ("DAZ Translucent", "Color", 4)),
    ("Translucency Gamma", ("DAZ Translucent", "Gamma", 1)),
    ("Translucency Strength", ("DAZ Translucent", "Fac", 1)),
    ("Translucency Scale", ("DAZ Translucent", "Scale", 1)),
    ("Translucency Radius", ("DAZ Translucent", "Radius", 3)),
    ("Translucency Cycles Mix Factor", ("DAZ Translucent", "Cycles Mix Factor", 1)),
    ("Translucency Eevee Mix Factor", ("DAZ Translucent", "Eevee Mix Factor", 1)),

    ("Principled", None),
    ("Principled Base Color", ("BSDF_PRINCIPLED", "Base Color", 4)),
    ("Principled Subsurface", ("BSDF_PRINCIPLED", "Subsurface", 1)),
    ("Principled Subsurface Radius", ("BSDF_PRINCIPLED", "Subsurface Radius", 3)),
    ("Principled Subsurface Color", ("BSDF_PRINCIPLED", "Subsurface Color", 4)),
    ("Principled Metallic", ("BSDF_PRINCIPLED", "Metallic", 1)),
    ("Principled Specular", ("BSDF_PRINCIPLED", "Specular", 1)),
    ("Principled Specular Tint", ("BSDF_PRINCIPLED", "Specular Tint", 1)),
    ("Principled Roughness", ("BSDF_PRINCIPLED", "Roughness", 1)),
    ("Principled Anisotropic", ("BSDF_PRINCIPLED", "Anisotropic", 1)),
    ("Principled Anisotropic Rotation",
     ("BSDF_PRINCIPLED", "Anisotropic Rotation", 1)),
    ("Principled Sheen", ("BSDF_PRINCIPLED", "Sheen", 1)),
    ("Principled Sheen Tint", ("BSDF_PRINCIPLED", "Sheen Tint", 1)),
    ("Principled Clearcoat", ("BSDF_PRINCIPLED", "Clearcoat", 1)),
    ("Principled Clearcoat Roughness", ("BSDF_PRINCIPLED", "Clearcoat Roughness", 1)),
    ("Principled IOR", ("BSDF_PRINCIPLED", "IOR", 1)),
    ("Principled Transmission", ("BSDF_PRINCIPLED", "Transmission", 1)),
    ("Principled Transmission Roughness",
     ("BSDF_PRINCIPLED", "Transmission Roughness", 1)),
    ("Principled Emission", ("BSDF_PRINCIPLED", "Emission", 4)),

    ("Top Coat", None),
    ("Top Coat Color", ("DAZ Top Coat", "Color", 4)),
    ("Top Coat Roughness", ("DAZ Top Coat", "Roughness", 1)),
    ("Top Coat Bump", ("DAZ Top Coat", "Bump", 1)),
    ("Top Coat Distance", ("DAZ Top Coat", "Distance", 1)),

    ("Overlay", None),
    ("Overlay Color", ("DAZ Overlay", "Color", 4)),
    ("Overlay Roughness", ("DAZ Overlay", "Roughness", 1)),
    ("Overlay Strength", ("DAZ Overlay", "Fac", 1)),

    ("Refraction", None),
    ("Refraction Color", ("DAZ Refraction", "Refraction Color", 4)),
    ("Refraction Roughness", ("DAZ Refraction", "Refraction Roughness", 1)),
    ("Refraction IOR", ("DAZ Refraction", "Refraction IOR", 1)),
    ("Refraction Fresnel IOR", ("DAZ Refraction", "Fresnel IOR", 1)),
    ("Refraction Glossy Color", ("DAZ Refraction", "Glossy Color", 4)),
    ("Refraction Glossy Roughness", ("DAZ Refraction", "Glossy Roughness", 1)),
    ("Refraction Strength", ("DAZ Refraction", "Fac", 1)),

    ("Transparent", None),
    ("Transparent Color", ("DAZ Transparent", "Color", 4)),
    ("Transparent Strength", ("DAZ Transparent", "Fac", 1)),

    ("Emission", None),
    ("Emission Color", ("DAZ Emission", "Color", 4)),
    ("Emission Strength", ("DAZ Emission", "Strength", 1)),
    ("Emission Strength", ("DAZ Emission", "Fac", 1)),

    ("Volume", None),
    ("Volume Absorption Color", ("DAZ Volume", "Absorbtion Color", 4)),
    ("Volume Absorption Density", ("DAZ Volume", "Absorbtion Density", 1)),
    ("Volume Scatter Color", ("DAZ Volume", "Scatter Color", 4)),
    ("Volume Scatter Density", ("DAZ Volume", "Scatter Density", 1)),
    ("Volume Scatter Anisotropy", ("DAZ Volume", "Scatter Anisotropy", 1)),

])


EnumsMaterials = [('BSDF', "BSDF", "BSDF (Cycles, full IRAY materials)"),
                  ('PRINCIPLED', "Principled", "Principled (Eevee and Cycles)")]

EnumsHair = [('HAIR_BSDF', "Hair BSDF", "Hair BSDF (Cycles)"),
             ('HAIR_PRINCIPLED', "Hair Principled", "Hair Principled (Cycles)"),
             ('PRINCIPLED', "Principled", "Principled (Eevee and Cycles)")]
