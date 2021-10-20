from daz_import.cgroup import CyclesGroup


class BackgroundGroup(CyclesGroup):
    def __init__(self):
        CyclesGroup.__init__(self)
        self.insockets += ["Color"]
        self.outsockets += ["Fac", "Color"]

    def create(self, node, name, parent):
        CyclesGroup.create(self, node, name, parent, 2)
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketFloat", "Fac")
        self.group.outputs.new("NodeSocketColor", "Color")

    def addNodes(self, args=None):
        lightpath = self.addNode("ShaderNodeLightPath", 1)
        self.links.new(
            lightpath.outputs["Is Camera Ray"], self.outputs.inputs["Fac"])
        self.links.new(
            self.inputs.outputs["Color"], self.outputs.inputs["Color"])
