from daz_import.Elements.Node import Node, Instance
from daz_import.Lib.Settings import Settings
from daz_import.Lib import VectorStatic


class CameraInstance(Instance):

    def setCameraProps(self, props):
        camera = self.node.data
        for key, value in props.items():
            if key == "znear":
                camera.clip_start = value * Settings.scale_
            elif key == "zfar":
                camera.clip_end = value * Settings.scale_
            elif key == "yfov":
                pass
            elif key == "focal_length":
                camera.lens = value
            elif key == "depth_of_field":
                camera.dof.use_dof = value
            elif key == "focal_distance":
                camera.dof.focus_distance = value * Settings.scale_
            elif key == "fstop":
                camera.dof.aperture_fstop = value
            else:
                print("Unknown camera prop: '%s' %s" % (key, value))

    def buildChannels(self, _):

        camera = self.rna.data
        camera.sensor_height = 64
        camera.sensor_fit = 'VERTICAL'
        
        for key, channel in self.channelsData.channels.items():
            value = channel["current_value"]
            if key == "Lens Shift X":
                camera.shift_x = value * Settings.scale_
            elif key == "Lens Shift Y":
                camera.shift_y = value * Settings.scale_
            elif key == "Focal Length":
                camera.lens = value         # in mm
            elif key == "DOF":
                camera.dof.use_dof = value
            elif key == "Depth of Field":
                camera.dof.focus_distance = value * Settings.scale_
            elif key == "Frame Width":
                # https://bitbucket.org/Diffeomorphic/import-daz/issues/75/better-cameras
                camera.sensor_height = value
            elif key == "Aspect Ratio":
                self.aspectRatio = value[1]/value[0]
            elif key == "Aperture Blades":
                camera.dof.aperture_blades = value
            elif key == "Aperture Blade Rotation":
                camera.dof.aperture_rotation = value*VectorStatic.D

            elif key in ["Point At", "Renderable", "Visible", "Selectable", "Perspective",
                         "Render Priority", "Cast Shadows", "Pixel Size",
                         "Lens Stereo Offset", "Lens Radial Bias", "Lens Stereo Offset",
                         "Lens Distortion Type", "Lens Distortion K1", "Lens Distortion K2", "Lens Distortion K3", "Lens Distortion Scale",
                         "DOF", "Aperature", "Disable Transform", "Visible in Simulation",
                         "Lens Thickness", "Settings Dimensions", "Dimension Preset", "Constrain Proportions",
                         "HeadlampMode", "Headlamp Intensity", "XHeadlampOffset", "YHeadlamp", "ZHeadlampOffset",
                         "Display Persistence", "Sight Line Opacity",
                         "Focal Point Scale", "FOV Color", "FOV Opacity", "FOV Length",
                         "DOF Plane Visibility", "DOF Plane Color",
                         "Visible in Viewport",
                         "DOF Overlay Color", "DOF Overlay Opacity", "Near DOF Plane Visibility", "Far DOF Plane Visibility",
                         ]:
                #print("Unused", key, value)
                pass
            else:
                print("Unknown camera channel '%s' %s" % (key, value))
