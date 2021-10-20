from daz_import.Lib.Settings import Settings, Settings
from daz_import.Lib.BlenderStatic import BlenderStatic


class RenderStatic:

    @classmethod
    def check(cls, context, force):
        from daz_import.light import getMinLightSettings

        renderSettingsCycles = {
            "Bounces": [("max_bounces", ">", 8)],
            "Diffuse": [("diffuse_bounces", ">", 1)],
            "Glossy": [("glossy_bounces", ">", 4)],
            "Transparent": [("transparent_max_bounces", ">", 16),
                            ("transmission_bounces", ">", 8),
                            ("caustics_refractive", "=", True)],
            "Volume": [("volume_bounces", ">", 4)],
        }

        renderSettingsEevee = {
            "Transparent": [
                ("use_ssr", "=", True),
                ("use_ssr_refraction", "=", True),
                ("use_ssr_halfres", "=", False),
                ("ssr_thickness", "<", 2 * Settings.unitScale),
                ("ssr_quality", ">", 1.0),
                ("ssr_max_roughness", ">", 1.0),
            ],
            "Bounces": [("shadow_cube_size", ">", "1024"),
                        ("shadow_cascade_size", ">", "2048"),
                        ("use_shadow_high_bitdepth", "=", True),
                        ("use_soft_shadows", "=", True),
                        ("light_threshold", "<", 0.001),
                        ("sss_samples", ">", 16),
                        ("sss_jitter_threshold", ">", 0.5),
                        ],
        }

        renderSettingsRender = {
            "Bounces": [("hair_type", "=", 'STRIP')],
        }

        lightSettings = {
            "Bounces": getMinLightSettings(),
        }

        scn = context.scene
        handle = Settings.handleRenderSettings
        if force:
            handle = "UPDATE"
        msg = ""
        msg += cls.checkSettings(scn.cycles, renderSettingsCycles,
                                 handle, "Cycles Settings", force)
        msg += cls.checkSettings(scn.eevee, renderSettingsEevee,
                                 handle, "Eevee Settings", force)
        msg += cls.checkSettings(scn.render, renderSettingsRender,
                                 handle, "Render Settings", force)

        handle = Settings.handleLightSettings
        if force:
            handle = "UPDATE"

        for light in BlenderStatic.visible_objects(context):
            if light.type == 'LIGHT':
                header = ('Light "%s" settings' % light.name)
                msg += cls.checkSettings(light.data, lightSettings,
                                         handle, header, force)

        if msg:
            msg += "See http://diffeomorphic.blogspot.com/2020/04/render-settings.html for details."
            print(msg)
            return msg
        else:
            return ""

    @staticmethod
    def checkSettings(engine, settings, handle, header, force):
        from daz_import.Elements.Material.MaterialStatic import MaterialStatic

        msg = ""
        if handle == "IGNORE":
            return msg
        ok = True
        for key, used in Settings.usedFeatures_.items():
            if (force or used) and key in settings.keys():
                for attr, op, minval in settings[key]:
                    if not hasattr(engine, attr):
                        continue
                    val = getattr(engine, attr)

                    fix, minval = MaterialStatic.checkSetting(
                        attr, op, val, minval, ok, header)
                    if fix:
                        ok = False
                        if handle == "UPDATE":
                            setattr(engine, attr, minval)
        if not ok:
            if handle == "WARN":
                msg = (
                    "%s are insufficient to render this scene correctly.\n" % header)
            else:
                msg = (
                    "%s have been updated to minimal requirements for this scene.\n" % header)
        return msg

    @classmethod
    def parse_options(cls, renderSettings, sceneSettings, backdrop, fileref):
        from .RenderOptions import RenderOptions

        if not Settings.useWorld_:
            return

        renderOptions = renderSettings["render_options"]
        elements = renderOptions.get("render_elements")

        if not elements:
            return

        if not Settings.render_:
            Settings.render_ = RenderOptions(fileref)

        Settings.render_.initSettings(sceneSettings, backdrop)
        
        for element in elements:
            Settings.render_.parse(element)
