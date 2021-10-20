
class DBZObject:
    def __init__(self, verts, uvs, edges,
                 faces, matgroups, props, lod, center):
                 
        self.verts = verts
        self.uvs = uvs
        self.edges = edges
        self.faces = faces
        self.matgroups = matgroups
        self.properties = props
        self.lod = lod
        self.center = center
