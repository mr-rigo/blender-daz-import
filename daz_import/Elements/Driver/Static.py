def removeModifiers(fcu):
    for mod in list(fcu.modifiers):
        fcu.modifiers.remove(mod)


def getShapekeyDriver(skeys, sname):
    return getRnaDriver(skeys, 'key_blocks["%s"].value' % (sname), None)


def getRnaDriver(rna, path, type=None):
    if rna and rna.animation_data:
        for fcu in rna.animation_data.drivers:
            if path == fcu.data_path:
                if not type:
                    return fcu
                for var in fcu.driver.variables:
                    if var.type == type:
                        return fcu
    return None
