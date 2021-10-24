import bpy
from bpy.types import ShaderNode


class MaterialGroup:
    def __init__(self, shader):
        from daz_import.Elements.Material import CyclesShader
        self.shader_object: CyclesShader = shader

        self.insockets = []
        self.outsockets = []

    def create(self, node: ShaderNode, name: str, parent, ncols: int):
        from daz_import.Elements.Material import CyclesShader
        from daz_import.Elements.ShaderGroup import ShaderGroup

        parent: CyclesShader
        group: ShaderGroup

        group = bpy.data.node_groups.new(name, 'ShaderNodeTree')

        self.shader_object.group = group

        node.name = name
        node.node_tree = group
        
        self.shader_object.set_material_object(group)
        self.shader_object.inputs = self.shader_object.add_node(
            "NodeGroupInput", 0)
        self.shader_object.outputs = self.shader_object.add_node(
            "NodeGroupOutput", ncols)

        self.shader_object.parent = parent
        self.shader_object.ncols = ncols

        return group

    def checkSockets(self, tree) -> bool:

        for socket in self.insockets:
            if socket not in tree.inputs.keys():
                print("Missing insocket: %s" % socket)
                return False

        for socket in self.outsockets:
            if socket not in tree.outputs.keys():
                print("Missing outsocket: %s" % socket)
                return False

        return True
