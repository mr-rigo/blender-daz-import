class DBZInfo:
    def __init__(self):
        self.objects = {}
        self.hdobjects = {}
        self.rigs = {}

    def fitFigure(self, inst, takenfigs):
        from daz_import.figure import FigureInstance
        from daz_import.Elements.Bone import BoneInstance

        name = inst.node.name

        if name in self.rigs.keys():
            if inst.id in takenfigs[name]:
                return
            elif inst.index < len(self.rigs[name]):
                restdata, transforms, center = self.rigs[name][inst.index]
                takenfigs[name].append(inst.id)
            else:
                print("Cannot fit %s" % name, inst.index, len(self.rigs[name]))
                return
        else:
            print("No fitting info for figure %s" % name)
            for key in self.rigs.keys():
                print("  ", key)
            return

        for child in inst.children.values():
            if isinstance(child, FigureInstance):
                self.fitFigure(child, takenfigs)
            elif isinstance(child, BoneInstance):
                self.fitBone(child, restdata, transforms, takenfigs)

    def fitBone(self, inst, restdata, transforms, takenfigs):
        from daz_import.figure import FigureInstance
        from daz_import.Elements.Bone import BoneInstance

        if inst.node.name not in restdata.keys():
            return
        inst.restdata = restdata[inst.node.name]
        rmat, wsloc, wsrot, wsscale = transforms[inst.node.name]

        for child in inst.children.values():
            if isinstance(child, FigureInstance):
                self.fitFigure(child, takenfigs)

            if isinstance(child, BoneInstance):
                self.fitBone(child, restdata, transforms, takenfigs)

    def tryGetName(self, name):
        replacements = [
            (" ", "_"),
            (" ", "-"),
            (".", "_"),
            (".", "-"),
        ]
        if name in self.objects.keys():
            return name
        else:
            name = name.replace("(", "_").replace(")", "_")
            for old, new in replacements:
                if name.replace(old, new) in self.objects.keys():
                    return name.replace(old, new)
        return None

    def getAlternatives(self, nname):
        return []
        alts = []
        for oname, data in self.objects.items():
            if nname == oname[:-2]:
                alts.append(data)
        return alts
