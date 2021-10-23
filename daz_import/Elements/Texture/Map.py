from bpy.types import Image
from daz_import.Elements.Color import ColorStatic



class Map:
    def __init__(self, map_: dict, ismask):

        self.url = None
        self.label = None
        self.operation = "alpha_blend"
        self.color = ColorStatic.WHITE
        self.ismask = ismask
        self.image = None
        self.size = None
        self.literal_image = None
        self.xoffset = 0
        self.yoffset = 0

        for key, default in [
            ("url", None),
            ("color", ColorStatic.BLACK),
            ("label", None),
            ("operation", "alpha_blend"),
            ("literal_image", None),
            ("invert", False),
            ("transparency", 1),
            ("rotation", 0),
            ("xmirror", False),
            ("ymirror", False),
            ("xscale", 1),
            ("yscale", 1),
            ("xoffset", 0),
                ("yoffset", 0)]:

            if key in map_.keys():
                setattr(self, key, map_[key])
            else:
                setattr(self, key, default)

    def __repr__(self):
        return ("<Map %s %s %s (%s %s)>" % (self.image, self.ismask, self.size, self.xoffset, self.yoffset))

    def build(self) -> Image:
        from daz_import.Elements.Image.ImageStatic import ImageStatic

        if self.image:
            return self.image
        elif self.url:
            self.image = ImageStatic.get_by_url(self.url)
            return self.image
        else:
            return self

    def get_image(self) -> Image:        
        return self.build()
