import os
import bpy
from daz_import.Lib import Registrar, BlenderStatic
from daz_import.Lib.Errors import DazPropsOperator, IsMesh
from bpy.props import BoolProperty
from .MaterialMerger import MaterialMerger


@Registrar()
class DAZ_OT_MergeMaterials(DazPropsOperator, MaterialMerger):
    bl_idname = "daz.merge_materials"
    bl_label = "Merge Materials"
    bl_description = "Merge identical materials"
    bl_options = {'UNDO'}
    
    pool = IsMesh.pool

    ignoreStrength: BoolProperty(
        name="Ignore Strength",
        description="Merge materials even if some scalar values differ.\nOften needed to merge materials with bump maps",
        default=False)

    ignoreColor: BoolProperty(
        name="Ignore Color",
        description="Merge materials even if some vector values differ",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "ignoreStrength")
        self.layout.prop(self, "ignoreColor")

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            self.mergeMaterials(ob)
            self.removeUnusedMaterials(ob)

    def keepMaterial(self, mn, mat, ob):
        for mat2 in self.matlist:
            if self.areSameMaterial(mat, mat2):
                self.reindex[mn] = self.assoc[mat2.name]
                self.newname[mat.name] = mat2.name
                return False
        return True

    def areSameMaterial(self, mat1, mat2):
        mname1 = mat1.name
        mname2 = mat2.name
        deadMatProps = [
            "texture_slots", "node_tree",
            "name", "name_full", "active_texture",
        ]
        deadMatProps.append("diffuse_color")
        matProps = self.getRelevantProps(mat1, deadMatProps)
        if not self.haveSameAttrs(mat1, mat2, matProps, mname1, mname2):
            return False
        if mat1.use_nodes and mat2.use_nodes:
            if self.areSameCycles(mat1.node_tree, mat2.node_tree, mname1, mname2):
                print(mat1.name, "=", mat2.name)
                return True
            else:
                return False
        else:
            return False

    @staticmethod
    def getRelevantProps(rna, deadProps):
        props = []
        for prop in dir(rna):
            if (prop[0] != "_" and
                    prop not in deadProps):
                props.append(prop)
        return props

    @classmethod
    def haveSameAttrs(cls, rna1, rna2, props, mname1, mname2):
        for prop in props:
            attr1 = attr2 = None
            if (prop[0] == "_" or
                prop[0:3] == "Daz" or
                    prop in ["select"]):
                pass
            elif hasattr(rna1, prop) and hasattr(rna2, prop):
                attr1 = getattr(rna1, prop)
                if prop == "name":
                    attr1 = cls.fixKey(attr1, mname1, mname2)
                attr2 = getattr(rna2, prop)
                if not cls.checkEqual(attr1, attr2):
                    return False
            elif hasattr(rna1, prop) or hasattr(rna2, prop):
                return False
        return True

    @classmethod
    def checkEqual(cls, attr1, attr2):
        if (isinstance(attr1, int) or
            isinstance(attr1, float) or
                isinstance(attr1, str)):
            return (attr1 == attr2)
        elif isinstance(attr1, bpy.types.Image):
            return (isinstance(attr2, bpy.types.Image) and (attr1.name == attr2.name))
        elif (isinstance(attr1, set) and isinstance(attr2, set)):
            return True
        elif hasattr(attr1, "__len__") and hasattr(attr2, "__len__"):
            if (len(attr1) != len(attr2)):
                return False
            for n in range(len(attr1)):
                if not cls.checkEqual(attr1[n], attr2[n]):
                    return False
        return True

    def areSameCycles(self, tree1, tree2, mname1, mname2):
        def rehash(struct):
            nstruct = {}
            for key, node in struct.items():
                if node.name[0:2] == "T_":
                    nstruct[node.name] = node
                elif node.type == 'GROUP':
                    nstruct[node.node_tree.name] = node
                else:
                    nstruct[key] = node
            return nstruct

        nodes1 = rehash(tree1.nodes)
        nodes2 = rehash(tree2.nodes)
        if not self.haveSameKeys(nodes1, nodes2, mname1, mname2):
            return False
        if not self.haveSameKeys(tree1.links, tree2.links, mname1, mname2):
            return False
        for key1, node1 in nodes1.items():
            key2 = self.fixKey(key1, mname1, mname2)
            node2 = nodes2[key2]
            if not self.areSameNode(node1, node2, mname1, mname2):
                return False
        for link1 in tree1.links:
            hit = False
            for link2 in tree2.links:
                if self.areSameLink(link1, link2, mname1, mname2):
                    hit = True
                    break
            if not hit:
                return False
        for link2 in tree2.links:
            hit = False
            for link1 in tree1.links:
                if self.areSameLink(link1, link2, mname1, mname2):
                    hit = True
                    break
            if not hit:
                return False
        return True

    def areSameNode(self, node1, node2, mname1, mname2):
        if node1.type != node2.type:
            return False
        if not self.haveSameKeys(node1, node2, mname1, mname2):
            return False
        deadNodeProps = ["dimensions", "location"]
        nodeProps = self.getRelevantProps(node1, deadNodeProps)
        if node1.type == 'GROUP':
            if node1.node_tree != node2.node_tree:
                return False
        elif not self.haveSameAttrs(node1, node2, nodeProps, mname1, mname2):
            return False
        if not self.haveSameInputs(node1, node2):
            return False
        return True

    @classmethod
    def areSameLink(cls, link1, link2, mname1, mname2):
        fromname1 = cls.getNodeName(link1.from_node)
        toname1 = cls.getNodeName(link1.to_node)

        fromname2 = cls.getNodeName(link2.from_node)
        toname2 = cls.getNodeName(link2.to_node)

        fromname1 = cls.fixKey(fromname1, mname1, mname2)
        toname1 = cls.fixKey(toname1, mname1, mname2)

        return (
            (fromname1 == fromname2) and
            (toname1 == toname2) and
            (link1.from_socket.name == link2.from_socket.name) and
            (link1.to_socket.name == link2.to_socket.name)
        )

    @staticmethod
    def getNodeName(node):
        if node.type == 'GROUP':
            return node.node_tree.name
        else:
            return node.name

    def haveSameInputs(self, node1, node2):
        if len(node1.inputs) != len(node2.inputs):
            return False
        for n, socket1 in enumerate(node1.inputs):
            socket2 = node2.inputs[n]
            if hasattr(socket1, "default_value"):
                if not hasattr(socket2, "default_value"):
                    return False
                val1 = socket1.default_value
                val2 = socket2.default_value
                if (hasattr(val1, "__len__") and
                        hasattr(val2, "__len__")):
                    if self.ignoreColor:
                        continue
                    for m in range(len(val1)):
                        if val1[m] != val2[m]:
                            return False
                elif val1 != val2 and not self.ignoreStrength:
                    return False
            elif hasattr(socket2, "default_value"):
                return False
        return True

    @staticmethod
    def fixKey(key, mname1, mname2):
        n = len(key) - len(mname1)

        if key[n:] == mname1:
            return key[:n] + mname2
        else:
            return key

    @classmethod
    def haveSameKeys(cls, struct1, struct2, mname1, mname2):
        m = len(mname1)
        for key1 in struct1.keys():
            if key1 in ["interface"]:
                continue

            key2 = cls.fixKey(key1, mname1, mname2)

            if key2 not in struct2.keys():
                return False
        return True

    @staticmethod
    def removeUnusedMaterials(ob):
        nmats = len(ob.data.materials)
        used = dict([(mn, False) for mn in range(nmats)])
        for f in ob.data.polygons:
            used[f.material_index] = True
        used = list(used.items())
        used.sort()
        used.reverse()
        for n, use in used:
            if not use:
                ob.data.materials.pop(index=n)

# ---------------------------------------------------------------------
#   Copy materials
# ---------------------------------------------------------------------
