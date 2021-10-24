import bpy
import os
from daz_import.Elements.Color import ColorStatic
from daz_import.Elements.Material import Material
from daz_import.Elements.Material.Cycles import CyclesMaterial, CyclesShader
from daz_import.Lib.Settings import Settings


class WorldMaterial(CyclesMaterial):

    def __init__(self, render, fileref):
        super().__init__(fileref)
        self.name = os.path.splitext(os.path.basename(fileref))[0] + " World"
        self.channelsData.channels = render.channelsData.channels
        self.background = None

        if render.background:
            self.background = self.srgbToLinearGamma22(render.background)

        self.backdrop = render.backdrop
        self.envmap = None

    def guessColor(self):
        return

    def build(self, context):
        if self.dontBuild():
            return

        mode = self.channelsData.getValue(["Environment Mode"], 3)
        # [Dome and Scene, Dome Only, Sun-Skies Only, Scene Only]

        if Settings.useWorld_ != 'ALWAYS' and mode == 3 and not self.background:
            print("Import scene only")
            return

        scn = context.scene
        self.envmap = self.channelsData.getChannel(["Environment Map"])
        scn.render.film_transparent = False

        if mode in [0, 1] and self.envmap:
            print("Draw environment", mode)
            if not self.channelsData.getValue(["Draw Dome"], False):
                print("Draw Dome turned off")
                scn.render.film_transparent = True
            elif self.channelsData.getImageFile(self.envmap) is None:
                print("Don't draw environment. Image file not found")
        else:
            self.envmap = None
            if self.background:
                print("Draw background", mode, self.background)
            else:
                scn.render.film_transparent = True
                self.background = ColorStatic.BLACK

        self.refractive = False
        Material.build(self, context)
        from .WorldTree import WorldTree

        self.tree = WorldTree(self)

        world = self.rna = bpy.data.worlds.new(self.name)

        world.use_nodes = True
        self.tree.build()
        scn.world = world

        if self.envmap is None:
            vis = world.cycles_visibility
            vis.camera = True
            vis.diffuse = False
            vis.glossy = False
            vis.transmission = False
            vis.scatter = False
