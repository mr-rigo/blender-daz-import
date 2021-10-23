import bpy
from bpy.types import ShaderNode


class MaterialGroup:
    def __init__(self, tree):
        from daz_import.Elements.Material import CyclesTree
        self.tree: CyclesTree = tree

        self.insockets = []
        self.outsockets = []

    def create(self, node: ShaderNode, name: str, parent, ncols: int):
        from daz_import.Elements.Material import CyclesTree
        
        parent: CyclesTree

        group = bpy.data.node_groups.new(name, 'ShaderNodeTree')

        self.tree.group = group

        node.name = name
        node.node_tree = group

        self.tree.nodes = group.nodes
        self.tree.links = group.links

        self.tree.inputs = self.tree.addNode("NodeGroupInput", 0)
        self.tree.outputs = self.tree.addNode("NodeGroupOutput", ncols)

        self.tree.parent = parent
        self.tree.ncols = ncols
        
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
