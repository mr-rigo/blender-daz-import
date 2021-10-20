import bpy
from daz_import.Lib import BlenderStatic
from daz_import.Lib.BlenderVertexStatic import BlenderVertexStatic


class Tesselator:
    def unTesselateFaces(self, context, hair, btn):
        self.squashFaces(hair)
        self.removeDoubles(context, hair, btn)
        deletes = self.checkTesselation(hair)
        if deletes:
            self.mergeRemainingFaces(hair, btn)

    def squashFaces(self, hair):
        verts = hair.data.vertices
        for f in hair.data.polygons:
            fverts = [verts[vn] for vn in f.vertices]
            if len(fverts) == 4:
                v1, v2, v3, v4 = fverts
                if (v1.co-v2.co).length < (v2.co-v3.co).length:
                    v2.co = v1.co
                    v4.co = v3.co
                else:
                    v3.co = v2.co
                    v4.co = v1.co

    def removeDoubles(self, context, hair, btn):
        BlenderStatic.active_object(context, hair)
        threshold = 0.001*btn.scale
        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.mesh.select_all(action='DESELECT')
        BlenderStatic.set_mode('OBJECT')

    def checkTesselation(self, hair):
        # Check that there are only pure lines

        vertedges = BlenderVertexStatic.getVertEdges(hair)
        nverts = len(hair.data.vertices)
        print("Check hair", hair.name, nverts)
        deletes = []
        for vn, v in enumerate(hair.data.vertices):
            ne = len(vertedges[vn])
            if ne > 2:
                #v.select = True
                deletes.append(vn)
        print("Number of vertices to delete", len(deletes))
        return deletes

    def mergeRemainingFaces(self, hair, btn):
        for f in hair.data.polygons:
            fverts = [hair.data.vertices[vn] for vn in f.vertices]
            r0 = fverts[0].co
            for v in fverts:
                v.co = r0
                v.select = True
        threshold = 0.001*btn.scale
        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        BlenderStatic.set_mode('OBJECT')

    def findStrands(self, hair):
        def getEdge(pair, mnum):
            return [min(pair), max(pair), mnum]

        pgs = hair.data.DazMatNums
        if len(pgs) >= len(hair.data.edges):
            edges = [getEdge(e.vertices, pgs[e.index].a)
                     for e in hair.data.edges]
        else:
            edges = [getEdge(e.vertices, 0) for e in hair.data.edges]
        edges.sort()
        plines = []
        v0 = -1
        for v1, v2, mnum in edges:
            if v1 == v0:
                pline.append(v2)
            else:
                pline = [v1, v2]
                plines.append((mnum, pline))
            v0 = v2
        strands = []
        verts = hair.data.vertices
        for mnum, pline in plines:
            strand = [verts[vn].co for vn in pline]
            strands.append((mnum, strand))
        return strands
