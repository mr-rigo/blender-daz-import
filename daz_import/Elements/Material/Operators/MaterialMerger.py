class MaterialMerger:
    def keepMaterial(self, *_):
        ...

    def mergeMaterials(self, ob):
        if ob.type != 'MESH':
            return

        self.matlist = []
        self.assoc = {}
        self.reindex = {}
        self.newname = {None: None}

        m = 0
        reduced = False
        for n, mat in enumerate(ob.data.materials):
            self.newname[mat.name] = mat.name
            if self.keepMaterial(n, mat, ob):
                self.matlist.append(mat)
                self.reindex[n] = self.assoc[mat.name] = m
                m += 1
            else:
                reduced = True
        if reduced:
            phairs = []
            for f in ob.data.polygons:
                f.material_index = self.reindex[f.material_index]
            for psys in ob.particle_systems:
                pset = psys.settings
                phairs.append((pset, pset.material_slot))
            for n, mat in enumerate(self.matlist):
                ob.data.materials[n] = mat
            for n in range(len(self.matlist), len(ob.data.materials)):
                ob.data.materials.pop()
            for pset, matslot in phairs:
                pset.material_slot = self.newname[matslot]
