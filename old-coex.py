import os
import csv
import math

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatProperty, IntProperty

bl_info = {
    "name": "clever-show animation (.csv)",
    "author": "Artem Vasiunik & Arthur Golubtsov",
    "version": (0, 5, 0),
    "blender": (2, 80, 0),
    # "api": 36079,
    "location": "File > Export > clever-show animation (.csv)",
    "description": "Export > clever-show animation (.csv)",
    "warning": "",
    "wiki_url": "https://github.com/CopterExpress/clever-show/blob/master/blender-addon/README.md",
    "tracker_url": "https://github.com/CopterExpress/clever-show/issues",
    "category": "Import-Export",
}


class ExportCsv(Operator, ExportHelper):
    bl_idname = "export_animation.folder"
    bl_label = "Export clever-show animation"
    filename_ext = ""
    use_filter_folder = True

    use_namefilter: bpy.props.BoolProperty(
        name="Use name filter for objects",
        default=False,
    )

    drones_name: bpy.props.StringProperty(
        name="Name identifier",
        description="Name identifier for all drone objects",
        default="clever",
    )

    show_warnings: bpy.props.BoolProperty(
        name="Show detailed animation warnings",
        default=True,
    )

    speed_warning_limit: bpy.props.FloatProperty(
        name="Speed limit",
        description="Limit of drone movement speed (m/s)",
        unit="VELOCITY",
        default=3,
        min=0,
    )
    drone_distance_limit: bpy.props.FloatProperty(
        name="Distance limit",
        description="Closest possible distance between drones (m)",
        unit="LENGTH",
        default=1.5,
        min=0,
    )

    filepath: StringProperty(
        name="File Path",
        description="File path used for exporting csv files",
        maxlen=1024,
        subtype="DIR_PATH",
        default="",
    )

    def execute(self, context):

        create_folder_if_does_not_exist(self.filepath)
        scene = context.scene
        objects = context.visible_objects

        drone_objects = []
        if self.use_namefilter:
            for drone_obj in objects:
                if self.drones_name.lower() in drone_obj.name.lower():
                    drone_objects.append(drone_obj)
        else:
            drone_objects = objects

        frame_start = scene.frame_start
        frame_end = scene.frame_end

        for drone_obj in drone_objects:
            with open(
                os.path.join(self.filepath, "{}.csv".format(drone_obj.name.lower())),
                "w",
            ) as csv_file:
                animation_file_writer = csv.writer(
                    csv_file, delimiter=",", quotechar="|", quoting=csv.QUOTE_MINIMAL
                )
                speed_exeeded = False
                distance_exeeded = False

                prev_x, prev_y, prev_z = 0, 0, 0

                animation_file_writer.writerow(
                    [os.path.splitext(bpy.path.basename(bpy.data.filepath))[0]]
                )

                for frame_number in range(frame_start, frame_end + 1):
                    scene.frame_set(frame_number)
                    rgb = get_rgb_from_object(drone_obj.name)
                    x, y, z = drone_obj.matrix_world.to_translation()
                    rot_z = drone_obj.matrix_world.to_euler("XYZ")[2]

                    speed = (
                        calc_speed((x, y, z), (prev_x, prev_y, prev_z))
                        if frame_number != frame_start
                        else 1
                    )
                    prev_x, prev_y, prev_z = x, y, z

                    if speed > self.speed_warning_limit:
                        speed_exeeded = True
                        if self.show_warnings:
                            self.report(
                                {"WARNING"},
                                "Speed of drone '%s' is greater than %s m/s (%s m/s) on frame %s"
                                % (
                                    drone_obj.name,
                                    round(self.speed_warning_limit, 5),
                                    round(speed, 5),
                                    frame_number,
                                ),
                            )

                    for second_drone_obj in drone_objects:
                        if second_drone_obj is not drone_obj:
                            x2, y2, z2 = second_drone_obj.matrix_world.to_translation()
                            distance = calc_distance((x, y, z), (x2, y2, z2))
                            if distance < self.drone_distance_limit:
                                distance_exeeded = True
                                if self.show_warnings:
                                    self.report(
                                        {"WARNING"},
                                        "Distance beteween drones '%s' and '%s' is less than %s m (%s m) on frame %s"
                                        % (
                                            drone_obj.name,
                                            second_drone_obj.name,
                                            round(self.drone_distance_limit, 5),
                                            round(distance, 5),
                                            frame_number,
                                        ),
                                    )

                    animation_file_writer.writerow(
                        [
                            str(frame_number),
                            round(x, 5),
                            round(y, 5),
                            round(z, 5),
                            # round(rot_z, 5),
                            *rgb,
                        ]
                    )

                if speed_exeeded:
                    self.report(
                        {"WARNING"}, "Drone '%s' speed limits exeeded" % drone_obj.name
                    )
                if distance_exeeded:
                    self.report(
                        {"WARNING"},
                        "Drone '%s' distance limits exeeded" % drone_obj.name,
                    )
                self.report(
                    {"WARNING"},
                    "Animation file exported for drone '%s'" % drone_obj.name,
                )
        return {"FINISHED"}


def create_folder_if_does_not_exist(folder_path):
    if os.path.isdir(folder_path):
        return
    os.mkdir(folder_path)


def get_rgb_from_object(object_name):
    """
    Получает цвет объекта на сцене Blender в формате RGB (целые числа от 0 до 255).

    Args:
        object_name: Строка, имя объекта.

    Returns:
        Кортеж (R, G, B) целых значений цвета в диапазоне [0, 255], или None, если объект не найден
        или не имеет материала.
    """
    obj = bpy.data.objects.get(object_name)

    if obj is None:
        print(f"Объект с именем '{object_name}' не найден.")
        return None

    if obj.type != "MESH":
        print(f"Объект '{object_name}' не является мешем, невозможно получить цвет.")
        return None

    if not obj.data.materials:
        print(f"Объект '{object_name}' не имеет привязанных материалов.")
        return None

    mat = obj.data.materials[0]  # Берем первый материал, если их несколько

    if mat.use_nodes:
        # Используем ноды материала
        node_tree = mat.node_tree
        output_node = next(
            (node for node in node_tree.nodes if node.type == "OUTPUT_MATERIAL"), None
        )

        if output_node:
            shader_input = next(
                (input for input in output_node.inputs if input.type == "SHADER"), None
            )
            if shader_input:
                shader_node = shader_input.links[0].from_node

                if shader_node.type == "BSDF_PRINCIPLED":
                    base_color_input = next(
                        (
                            input
                            for input in shader_node.inputs
                            if input.name == "Base Color"
                        ),
                        None,
                    )
                    if base_color_input:
                        color = base_color_input.default_value[:3]
                        rgb_color = tuple(
                            int(c * 255) for c in color
                        )  # Конвертация в RGB (0-255)
                        return rgb_color
                    else:
                        print(
                            f"Не найден вход 'Base Color' в шейдере принципиального BSDF для объекта '{object_name}'."
                        )
                else:
                    print(
                        f"Первый вход шейдера не является 'Принципиальный BSDF' для объекта '{object_name}'."
                    )
            else:
                print(
                    f"У выходного нода не найден вход шейдера для объекта '{object_name}'."
                )
        else:
            print(f"Не найден выходной нод материала для объекта '{object_name}'.")

    else:
        # Используем цвет diffuse (если не ноды)
        color = mat.diffuse_color[:3]
        rgb_color = tuple(int(c * 255) for c in color)  # Конвертация в RGB (0-255)
        print("Используются не ноды")
        return rgb_color

    return None


def calc_speed(start_point, end_point):
    time_delta = 0.1
    distance = calc_distance(start_point, end_point)
    return distance / time_delta


def calc_distance(start_point, end_point):
    distance = math.sqrt(
        (start_point[0] - end_point[0]) ** 2
        + (start_point[1] - end_point[1]) ** 2
        + (start_point[2] - end_point[2]) ** 2
    )
    return distance


def menu_func(self, context):
    self.layout.operator(ExportCsv.bl_idname, text="clever-show animation (.csv)")


def register():
    bpy.utils.register_class(ExportCsv)
    bpy.types.TOPBAR_MT_file_export.append(menu_func)


def unregister():
    bpy.utils.unregister_class(ExportCsv)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)


if __name__ == "__main__":
    register()
