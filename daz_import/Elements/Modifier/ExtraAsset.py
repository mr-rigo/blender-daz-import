from typing import List, Dict
from daz_import.Elements.Assets.Asset import Asset
from daz_import.Elements.Assets.Channels import Channels
from .Modifier import Modifier


class ExtraAsset(Modifier):
    def __init__(self, fileref):
        super().__init__(fileref)
        self.channelsData: Channels = Channels(self)
        self.extras = {}
        self.type = None

    def __repr__(self):
        return ("<Extra %s %s p: %s>" % (self.id, list(self.extras.keys()), self.parent))

    def parse(self, data: dict):
        super().parse(data)
        self.channelsData.parse(data)
        extras: List[Dict] = data.get("extra", [])

        if not isinstance(extras, list):
            extras = [extras]

        for extra in extras:
            if etype := extra.get("type"):
                self.extras[etype] = extra

    def update(self, struct):
        super().update(struct)
        self.channelsData.update(struct)
        if "extra" not in struct.keys():
            return
        extras = struct["extra"]
        if not isinstance(extras, list):
            extras = [extras]
        for extra in extras:
            if "type" in extra.keys():
                etype = extra["type"]
                if etype in self.extras.keys():
                    for key, value in extra.items():
                        self.extras[etype][key] = value
                else:
                    self.extras[etype] = extra

    def preprocess(self, inst):
        geonode = self.getGeoNode(inst)
        if geonode is None:
            return

        if "studio_modifier_channels" in self.extras.keys():
            geonode.modifiers[self.name] = self
            modchannels = self.extras["studio_modifier_channels"]
            for cstruct in modchannels["channels"]:
                channel = cstruct["channel"]
                self.channelsData.setChannel(channel)

        if "studio/modifier/push" in self.extras.keys():
            geonode.push = self.channelsData.getValue(["Value"], 0)

    def build(self, context, inst):
        if inst is None:
            return
        for etype, extra in self.extras.items():
            #print("EE '%s' '%s' %s %s" % (inst.name, self.name, self.parent, etype))
            if etype == "studio/modifier/dynamic_generate_hair":
                from daz_import.dforce import DynGenHair
                inst.dyngenhair = DynGenHair(inst, self, extra)
            elif etype == "studio/modifier/dynamic_simulation":
                from daz_import.dforce import DynSim
                inst.dynsim = DynSim(inst, self, extra)
            elif etype == "studio/modifier/dynamic_hair_follow":
                from daz_import.dforce import DynHairFlw
                inst.dynhairflw = DynHairFlw(inst, self, extra)
            elif etype == "studio/modifier/line_tessellation":
                from daz_import.dforce import LinTess
                inst.lintess = LinTess(inst, self, extra)
            elif etype == "studio/simulation_settings/dynamic_simulation":
                from daz_import.dforce import SimSet
                simset = SimSet(inst, self, extra)
                inst.simsets.append(simset)
            elif etype == "studio/node/dform":
                print("DFORM", self)

    def getGeoNode(self, inst: Asset) -> Asset:
        if inst.is_instense('Instance') and inst.geometries:
            return inst.geometries[0]
        elif inst.is_instense('GeoNode'):
            return inst
        else:
            return None
