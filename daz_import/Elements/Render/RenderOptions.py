from daz_import.Elements.Assets import Asset
from daz_import.Elements.Assets.Channels import Channels
from daz_import.Lib.Settings import Settings


class RenderOptions(Asset):
    def __init__(self, fileref):
        super().__init__(fileref)
        self.channelsData = Channels(self)
        self.world = None
        self.background = None
        self.backdrop = None

    def initSettings(self, data: dict, backdrop):
        if "backdrop_visible" in data.keys()\
                and not data["backdrop_visible"]:
            return
        if "backdrop_visible_in_render" in data.keys()\
                and not data["backdrop_visible_in_render"]:
            return

        if backdrop:
            self.backdrop = backdrop

        if value := data.get("background_color"):
            self.background = value

    def __repr__(self):
        return ("<RenderOptions %s %s>" % (self.background, self.backdrop))

    def parse(self, data: dict):
        Asset.parse(self, data)
        self.channelsData.parse(data)

        for child in data.get("children", []):
            for channel in child.get("channels", []):
                self.channelsData.setChannel(channel["channel"])

    def update(self, struct):
        Asset.update(self, struct)
        self.channelsData.update(struct)

    def build(self, context):
        if Settings.useWorld_ == 'NEVER':
            return

        from .WorldMaterial import WorldMaterial
        self.world = WorldMaterial(self, self.fileref)
        self.world.build(context)
