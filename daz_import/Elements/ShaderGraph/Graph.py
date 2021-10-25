from bpy.types import Material, NodeSocket
from bpy.types import ShaderNode, NodeLinks, Nodes, NodeTree
from typing import Any


class ShaderNodeAbstract:
    alias: str = None

    def __init__(self, graph):
        self.graph: ShaderGraph = graph
        if not self.alias:
            raise AttributeError('Unknown shader alias')
        self.inner_node = self.graph.create_by_key(self.alias)


class ShaderProperyInput:
    def __init__(self,  node, key: str) -> None:
        self.node: ShaderNodeAbstract = node
        self.key = key

    def __iadd__(self, other):
        self.node.graph.connect(self, other)
        return self

    def inner(self) -> NodeSocket:
        return self.node.inner_node.inputs.get(self.key)

    def default(self, value: Any):
        prop: Any = self.inner()

        try:
            prop.default_value = value
        except:
            print('- Error set default value shader node', self.key, prop)


class ShaderProperyOutput(ShaderProperyInput):
    def inner(self) -> NodeSocket:
        return self.node.inner_node.outputs.get(self.key)


class ShaderOutput(ShaderNodeAbstract):
    alias = 'ShaderNodeOutputMaterial'

    def __init__(self, graph):
        super().__init__(graph)
        self.surface = ShaderProperyInput(self, 'Surface')


class BSDFPrincipled(ShaderNodeAbstract):
    alias = 'ShaderNodeBsdfPrincipled'

    def __init__(self, graph):
        super().__init__(graph)
        self.output = ShaderProperyOutput(self, 'BSDF')
        self.diffuse = ShaderProperyInput(self, 'Base Color')
        self.specular = ShaderProperyInput(self, 'Specular')


class DiffuseShader(ShaderNodeAbstract):
    alias = 'ShaderNodeBsdfDiffuse'

    def __init__(self, graph):
        super().__init__(graph)
        self.output = ShaderProperyOutput(self, 'BSDF')
        self.diffuse = ShaderProperyInput(self, 'Color')
        self.roughness = ShaderProperyInput(self, 1)
        self.normal = ShaderProperyInput(self, 'Normal')


class EmissionShader(ShaderNodeAbstract):
    alias = 'ShaderNodeEmission'

    def __init__(self, graph):
        super().__init__(graph)
        self.input = ShaderProperyInput(self, 'Color')
        self.emisssion = ShaderProperyInput(self, 'Color')
        self.output = ShaderProperyOutput(self, 'Emission')
        self.power = ShaderProperyInput(self, 1)


class ShaderGraph:
    def __init__(self, material: Material = None):
        self.material: Material = None
        self.nodes: Nodes = None
        self.links: NodeLinks = None
        self.__output_shader = None
        if material:
            self.init(material)

    def use_nodes(self, value=True):
        if self.material:
            self.material.use_nodes = value

    def createNode(self) -> ShaderNodeAbstract:
        return ShaderNodeAbstract(self)

    def connect(self, a, b):
        if isinstance(a, ShaderProperyInput):
            a = a.inner()

        if isinstance(b, ShaderProperyInput):
            b = b.inner()

        self.links.new(a, b)

    def set_alpha(self, blend='HASHED'):
        # ['OPAQUE', 'CLIP', 'HASHED', 'BLEND']
        if self.material:
            self.material.blend_method = blend
        #mat.use_screen_refraction = useRefraction
        #mat.shadow_method = 'HASHED'
        #mat.shadow_method = 'HASHED'

    def create_by_key(self, key: str) -> ShaderNode:
        return self.nodes.new(key)

    def clear(self):
        self.nodes.clear()

    def get_output(self) -> ShaderOutput:
        if not self.__output_shader:
            self.__output_shader = ShaderOutput(self)
        return self.__output_shader

    def init(self, obj, matrial=True):
        if not obj:
            return

        if matrial:
            obj: Material
            obj.use_nodes = True
            self.material = obj
            obj = obj.node_tree

        self.nodes = obj.nodes
        self.links = obj.links
        # self.nodes = self.material.node_tree.nodes
        # self.links = self.material.node_tree.links

    def set_active_node(self, node: ShaderNode):
        self.nodes.active = node
