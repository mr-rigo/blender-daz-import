import bpy


class MaterialGroup:
    def __init__(self):
        from daz_import.Elements.Material import CyclesTree

        self.insockets = []
        self.outsockets = []
        self.__tree: CyclesTree = self

    def create(self, node, name, parent, ncols):
        self.group = bpy.data.node_groups.new(name, 'ShaderNodeTree')

        node.name = name
        node.node_tree = self.group

        self.__tree.nodes = self.group.nodes
        self.__tree.links = self.group.links
        self.__tree.inputs = self.addNode("NodeGroupInput", 0)
        self.__tree.outputs = self.addNode("NodeGroupOutput", ncols)
        self.__tree.parent = parent
        self.__tree.ncols = ncols

    def checkSockets(self, tree) -> bool:
        
        for socket in self.mat_group.insockets:
            if socket not in tree.inputs.keys():
                print("Missing insocket: %s" % socket)
                return False

        for socket in self.outsockets:            
            if socket not in tree.outputs.keys():
                print("Missing outsocket: %s" % socket)
                return False

        return True
