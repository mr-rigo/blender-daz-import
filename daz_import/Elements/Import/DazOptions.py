from daz_import.Lib.Files import DazImageFile
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import *

from daz_import.utils import *



class DazOptions(DazImageFile):

    skinColor: FloatVectorProperty(
        name="Skin",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.6, 0.4, 0.25, 1.0)
    )

    clothesColor: FloatVectorProperty(
        name="Clothes",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.09, 0.01, 0.015, 1.0)
    )

    fitMeshes: EnumProperty(
        items=[('SHARED', "Unmorphed Shared (Environments)", "Don't fit meshes. All objects share the same mesh.\nFor environments with identical objects like leaves"),
               ('UNIQUE', "Unmorped Unique (Environments)",
                "Don't fit meshes. Each object has unique mesh instance.\nFor environments with objects with same mesh but different materials, like paintings"),
               ('MORPHED', "Morphed (Characters)",
                "Don't fit meshes, but load shapekeys.\nNot all shapekeys are found.\nShapekeys are not transferred to clothes"),
               ('DBZFILE', "DBZ File (Characters)",
                "Use exported .dbz (.json) file to fit meshes. Must exist in same directory.\nFor characters and other objects with morphs"),
               ],
        name="Mesh Fitting",
        description="Mesh fitting method",
        default='MORPHED')

    morphStrength: FloatProperty(
        name="Morph Strength",
        description="Morph strength",
        default=1.0)

    def draw(self, context):
        box = self.layout.box()
        box.label(text="Mesh Fitting")
        box.prop(self, "fitMeshes", expand=True)
        if self.fitMeshes == 'MORPHED':
            box.prop(self, "morphStrength")
        self.layout.separator()
        box = self.layout.box()
        box.label(text="Viewport Color")
        if Settings.viewportColors == 'GUESS':
            row = box.row()
            row.prop(self, "skinColor")
            row.prop(self, "clothesColor")
        else:
            box.label(text=Settings.viewportColors)
