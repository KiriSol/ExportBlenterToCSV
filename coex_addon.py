import os
import csv
import math

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, FloatProperty


# Информация для блендера
bl_info = {
    "name": "coex-v.1 (.csv)",
    "author": "Kirill Solovey",
    "version": (0, 5, 0),
    "blender": (2, 80, 0),
    # "api": 36079,
    "location": "File > Export > coex-v.1 (.csv)",
    "description": "Это аддон для экспорта анимации каждого объекта в отдельные текстовые файлы: <name-obj>.csv",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "DroneShow",
}

PRINT_LOGS = True


class ExportCsv(Operator, ExportHelper):
    bl_idname = "export_animation.folder"
    bl_label = "Export drone show animation"  # Кнопка старта экспорта
    filename_ext = ""
    use_filter_folder = True

    # Элементы GUI
    # region
    use_nameFilter: BoolProperty(
        name="Filter",
        description="Использование фильтра для объектов",
        default=False,
    )  # type: ignore

    drones_name: StringProperty(
        name="Name identifier",
        description="Идентификатор имени для всех дронов",
        default="",
    )  # type: ignore

    show_warnings: BoolProperty(
        name="Показывать подробные анимационные предупреждения",
        default=False,
    )  # type: ignore

    speed_warning_limit: FloatProperty(
        name="Speed limit",
        description="Limit of drone movement speed (m/s)",
        unit="VELOCITY",
        default=2,
        min=0,
    )  # type: ignore

    drone_distance_limit: FloatProperty(
        name="Distance limit",
        description="Closest possible distance between drones (m)",
        unit="LENGTH",
        default=1,
        min=0,
    )  # type: ignore

    # Что нужно экспортировать

    showFrame_number: BoolProperty(
        name="FrameNumber",
        description="Показывать номер кадра в выходном файле",
        default=True,
    )  # type: ignore

    showXYZ: BoolProperty(
        name="XYZ",
        description="Показывать x, y, z в выходном файле",
        default=True,
    )  # type: ignore

    showYAW: BoolProperty(
        name="Yaw",
        description="Показывать поворот относительно оси Z, хз зачем, но пусть будет",
        default=False,
    )  # type: ignore

    showRGB: BoolProperty(
        name="RGB",
        description="Показывать цвета ф формате rgb [0 - 255] в выходном файле",
        default=True,
    )  # type: ignore

    # Окно проводника с вводом названия директории для выходных файлов
    filepath: StringProperty(
        name="File Path",
        description="File path used for exporting csv files",
        maxlen=1024,
        subtype="DIR_PATH",
        default="",
    )  # type: ignore

    # endregion

    def execute(self, context: bpy.types.Context) -> set[str]:
        create_folder_if_not_exists(
            self.filepath
        )  # Создание директории с выходными файлами

        # Получение списка дронов
        drone_objects: list[bpy.types.Object] = []
        if self.use_nameFilter:
            for drone_obj in context.visible_objects:
                if self.drones_name in drone_obj.name:
                    drone_objects.append(drone_obj)
        else:
            drone_objects = context.visible_objects

        # Получение начального и конечного кадра
        frame_start: int = context.scene.frame_start
        frame_end: int = context.scene.frame_end

        # Цикл по всем дронам
        for drone_obj in drone_objects:
            with open(
                os.path.join(self.filepath, "{}.csv".format(drone_obj.name.lower())),
                "w",
            ) as csv_file:  # Создание csv-файла

                animation_file_writer = csv.writer(
                    csv_file, delimiter=",", quotechar="|", quoting=csv.QUOTE_MINIMAL
                )

                speed_exeeded = distance_exeeded = False
                prev_x = prev_y = prev_z = 0

                # Первая строка в csv-файле - имя дрона на анимации
                animation_file_writer.writerow(
                    [os.path.splitext(bpy.path.basename(bpy.data.filepath))[0]]
                )

                for frame_number in range(
                    frame_start, frame_end + 1
                ):  # Цикл по всем кадрам

                    context.scene.frame_set(frame_number)  # Переключение кадра

                    rgb: tuple[int, int, int] = get_rgb_from_obj(
                        drone_obj
                    )  # Получение цвета
                    x, y, z = (
                        drone_obj.matrix_world.to_translation()
                    )  # Получение координат
                    rot_z = drone_obj.matrix_world.to_euler("XYZ")[
                        2
                    ]  # Получение поворота

                    speed: float = (
                        calc_speed((x, y, z), (prev_x, prev_y, prev_z))
                        if frame_number != frame_start
                        else 1
                    )  # Расчет скорости

                    # Получение предыдущих координат для расчета скорости
                    prev_x, prev_y, prev_z = x, y, z

                    if speed > self.speed_warning_limit:  # Проверка скорости
                        speed_exeeded = True
                        if self.show_warnings:  # Подробные предупреждения
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

                    for (
                        second_drone_obj
                    ) in drone_objects:  # Проверка расстояний до других дронов
                        if second_drone_obj is not drone_obj:
                            x2, y2, z2 = (
                                second_drone_obj.matrix_world.to_translation()
                            )  # Получение координат
                            distance = calc_distance(
                                (x, y, z), (x2, y2, z2)
                            )  # Подсчет расстояния
                            if distance < self.drone_distance_limit:
                                distance_exeeded = True
                                if self.show_warnings:  # Подробные предупреждения
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

                    # Запись данных в csv-файл с проверкой

                    drone_data: tuple[
                        tuple[int],
                        tuple[float, float, float],
                        tuple[float],
                        tuple[int, int, int],
                    ] = (
                        (frame_number,),
                        tuple(map(lambda x: round(x, 5), (x, y, z))),
                        (round(rot_z, 5),),
                        rgb,
                    )
                    write_to_file = []

                    for i, is_show in enumerate(
                        (
                            self.showFrame_number,
                            self.showXYZ,
                            self.showYAW,
                            self.showRGB,
                        )
                    ):
                        if is_show:
                            write_to_file += drone_data[i]

                    animation_file_writer.writerow(tuple(write_to_file))

                # Вывод предупреждений и сообщение об успешном экспорте
                if speed_exeeded:
                    self.report(
                        {"WARNING"},
                        f"Drone '{drone_obj.name}' speed limits exeeded",
                    )
                if distance_exeeded:
                    self.report(
                        {"WARNING"},
                        f'Drone "{drone_obj.name}" distance limits exeeded',
                    )
                self.report(
                    {"WARNING"},
                    f'Animation file exported for drone "{drone_obj.name}"',
                )

        return {"FINISHED"}


# Функции (Вроде нормально работают)


def create_folder_if_not_exists(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def get_rgb_from_obj(obj: bpy.types.Object) -> tuple[int, int, int]:
    """
    Получает цвет объекта на сцене Blender в формате RGB

    Args:
        obj: Объект Blender

    Returns:
        Кортеж (R, G, B) целых значений цвета в диапазоне [0, 255]
    """

    def get_rgb() -> tuple[int, int, int]:
        # Проверка правильности объекта
        if obj.type != "MESH":
            raise ValueError(
                f"Объект '{obj.name}' не является мешем, невозможно получить цвет."
            )
        if not obj.data.materials:
            raise ValueError(f"Объект '{obj.name}' не имеет привязанных материалов.")

        mat = obj.data.materials[0]  # Берем первый материал, если их несколько

        if not mat.use_nodes:
            # print("Используются не ноды")
            return (
                int(c * 255)  # Конвертация в RGB (0-255)
                for c in mat.diffuse_color[:3]  #
            )

        # TODO: обработку нод объекта
        raise ValueError("Используются ноды")

    try:
        return get_rgb()
    except ValueError as err:
        if PRINT_LOGS:
            print(
                f"\033[31m[ValueError: from addon '{bl_info['name']}'] Не удалось получить цвет: {err}\033[0m"
            )
        return (0, 0, 0)
    except:
        if PRINT_LOGS:
            print(
                f"\033[31m[Error: from addon '{bl_info['name']}'] Не удалось получить цвет: {err}\033[0m"
            )
        return (0, 0, 0)


def calc_speed(
    start_point: tuple[float, float, float],
    end_point: tuple[float, float, float],
    time_delta: float = 0.1,
) -> float:

    distance: float = calc_distance(start_point, end_point)
    return distance / time_delta


def calc_distance(
    start_point: tuple[float, float, float], end_point: tuple[float, float, float]
) -> float:
    # Подсчет расстояния по формуле дистанции в 3D
    distance: float = math.sqrt(
        (start_point[0] - end_point[0]) ** 2
        + (start_point[1] - end_point[1]) ** 2
        + (start_point[2] - end_point[2]) ** 2
    )
    return distance


"""Установка и удаление аддона"""


def menu_func(self, context) -> None:
    self.layout.operator(ExportCsv.bl_idname, text="coex-v.1 (.csv)")


def register() -> None:
    bpy.utils.register_class(ExportCsv)
    bpy.types.TOPBAR_MT_file_export.append(menu_func)


def unregister() -> None:
    bpy.utils.unregister_class(ExportCsv)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)


if __name__ == "__main__":
    register()
