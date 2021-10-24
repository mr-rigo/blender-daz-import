from daz_import.Elements.ShaderGroup import ShaderGroup


class BackgroundGroup(ShaderGroup):
    
    def __init__(self):
        super().__init__()
        
        

    def create(self, node, name, parent):
        super().create(node, name, parent, 2)

        self.input("NodeSocketColor", "Color")
        self.output("NodeSocketFloat", "Fac")
        self.output("NodeSocketColor", "Color")

    def addNodes(self, _=None):
        lightpath = self.add_node("ShaderNodeLightPath", 1)
        
        self.links.new(
            lightpath.outputs["Is Camera Ray"], self.outputs.inputs["Fac"])
        self.links.new(
            self.inputs.outputs["Color"], self.outputs.inputs["Color"])
