

class CyclesStatic:
    NCOLUMNS = 20
    XSIZE = 300
    YSIZE = 250

    @classmethod
    def findTexco(cls, tree, col):
        if nodes := cls.findNodes(tree, "TEX_COORD"):
            return nodes[0]
        else:
            return tree.addNode("ShaderNodeTexCoord", col)

    @staticmethod
    def findNodes(tree, nodeType):
        nodes = []
        for node in tree.nodes.values():
            if node.type == nodeType:
                nodes.append(node)
        return nodes

    @classmethod
    def findNode(cls, tree, ntypes):
        if isinstance(ntypes, list):
            for ntype in ntypes:
                node = cls.findNode(tree, ntype)
                if node:
                    return node
        for node in tree.nodes:
            if node.type == ntypes:
                return node
        return None

    @staticmethod
    def findLinksFrom(tree, ntype):
        links = []
        for link in tree.links:
            if link.from_node.type == ntype:
                links.append(link)
        return links

    @staticmethod
    def findLinksTo(tree, ntype):
        links = []
        for link in tree.links:
            if link.to_node.type == ntype:
                links.append(link)
        return links

    @staticmethod
    def getLinkTo(tree, node, slot):
        for link in tree.links:
            if (link.to_node == node and
                    link.to_socket.name == slot):
                return link
        return None

    @staticmethod
    def pruneNodeTree(shader):
        marked = {}
        output = False

        for node in shader.nodes:
            marked[node.name] = False
            if "Output" in node.name:
                marked[node.name] = True
                output = True

        if not output:
            print("No output node")
            return marked

        nmarked = 0
        n = 1

        while n > nmarked:
            nmarked = n
            n = 1
            for link in shader.links:
                if marked[link.to_node.name]:
                    marked[link.from_node.name] = True
                    n += 1

        for node in shader.nodes:
            node.select = False
            if not marked[node.name]:
                shader.nodes.remove(node)

        return marked

    @classmethod
    def create_cycles_tree(cls, mat):
        tree = cls(None)
        tree.nodes = mat.node_tree.nodes
        tree.links = mat.node_tree.links
        return tree
