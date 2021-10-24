from bpy.types import Material, NodeSocket
from bpy.types import ShaderNode
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
        self.node.graph.link(self, other)
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


class ShaderGraph:
    def __init__(self, material: Material):
        self.material = material
        self.graph = self.material.node_tree
        self.__output_shader = None
        self.use_nodes()
        self.clear()

        self.output = self.get_output()

    def use_nodes(self, value=True):
        self.material.use_nodes = value

    def createNode(self) -> ShaderNodeAbstract:
        return ShaderNodeAbstract(self)

    def link(self, a, b):
        if isinstance(a, ShaderProperyInput):
            a = a.inner()

        if isinstance(b, ShaderProperyInput):
            b = b.inner()

        self.material.node_tree.links.new(a, b)

    def set_alpha(self, blend='HASHED'):
        # ['OPAQUE', 'CLIP', 'HASHED', 'BLEND']
        self.material.blend_method = blend
        #mat.use_screen_refraction = useRefraction
        #mat.shadow_method = 'HASHED'
        #mat.shadow_method = 'HASHED'

    def create_by_key(self, key: str) -> ShaderNode:
        return self.material.node_tree.nodes.new(key)

    def clear(self):
        self.material.node_tree.nodes.clear()

    def get_output(self) -> ShaderOutput:
        if not self.__output_shader:
            self.__output_shader = ShaderOutput(self)
        return self.__output_shader
