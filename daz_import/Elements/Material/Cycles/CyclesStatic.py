
class CyclesStatic:
    NCOLUMNS = 20
    XSIZE = 300
    YSIZE = 250

    @classmethod
    def findNode(cls, shader, key):
        for node in shader.nodes:
            if node.type != key:
                continue
            return node

    @staticmethod
    def findLinksTo(shader, ntype):
        links = []
        for link in shader.links:
            if link.to_node.type == ntype:
                links.append(link)

        return links

    @staticmethod
    def getLinkTo(shader, node, slot):
        for link in shader.links:
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
