class UDimStatic:

    @classmethod
    def add(cls, mat, udim, vdim):
        if mat.node_tree:
            cls.add_tree(mat.node_tree, udim, vdim)
        else:
            for mtex in mat.texture_slots:
                if mtex and mtex.texture and mtex.texture.extension == 'CLIP':
                    mtex.offset[0] += udim
                    mtex.offset[1] += vdim

    @classmethod
    def add_tree(cls, tree, udim, vdim):
        if tree is None:
            return
        for node in tree.nodes:
            if node.type == 'MAPPING':
                if hasattr(node, "translation"):
                    slot = node.translation
                else:
                    slot = node.inputs["Location"].default_value
                slot[0] += udim
                slot[1] += vdim
            elif node.type == 'GROUP':
                cls.add_tree(node.node_tree, udim, vdim)

    @staticmethod
    def shiftUVs(mat, mn, ob, tile):
        ushift = tile - mat.DazUDim
        print(" Shift", mat.name, mn, ushift)
        uvloop = ob.data.uv_layers.active
        m = 0
        
        for _, f in enumerate(ob.data.polygons):
            if f.material_index == mn:
                for _ in range(len(f.vertices)):
                    uvloop.data[m].uv[0] += ushift
                    m += 1
            else:
                m += len(f.vertices)
