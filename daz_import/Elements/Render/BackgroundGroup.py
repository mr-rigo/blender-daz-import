from daz_import.Elements.ShaderGroup import ShaderGroup


class BackgroundGroup(ShaderGroup):
    
    def __init__(self):
        super().__init__()
        self.mat_group.insockets += ["Color"]
        self.mat_group.outsockets += ["Fac", "Color"]

    def create(self, node, name, parent):
        super().create(node, name, parent, 2)

        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.outputs.new("NodeSocketFloat", "Fac")
        self.group.outputs.new("NodeSocketColor", "Color")

    def addNodes(self, _=None):
        lightpath = self.addNode("ShaderNodeLightPath", 1)
        
        self.links.new(
            lightpath.outputs["Is Camera Ray"], self.outputs.inputs["Fac"])
        self.links.new(
            self.inputs.outputs["Color"], self.outputs.inputs["Color"])
