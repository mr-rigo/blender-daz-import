from daz_import.Elements.Material import Material
from daz_import.Elements.Material.Cycles import CyclesMaterial


class HairMaterial(CyclesMaterial):

    def __init__(self, name, color):
        super().__init__(name)
        self.name = name
        self.color = color
        # self.isHair = True

    def guessColor(self):
        if self.rna:
            self.rna.diffuse_color = self.color

    def build(self, context, color):
        if self.dontBuild():
            return
        super().build(self, context)

        self.rna.diffuse_color[0:3] = self.color

    @staticmethod
    def buildHairMaterial(mname, color, context, force=False):
        color = list(color[0:3])
        hmat = HairMaterial(mname, color)
        hmat.force = force
        hmat.build(context, color)
        return hmat.rna
