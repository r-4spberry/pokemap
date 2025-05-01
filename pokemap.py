import os
import tkinter as tk
from tkinter import filedialog
import json
import cv2
import numpy as np
import dearpygui.dearpygui as dpg
import base64


dpg.create_context()


def encode_image_to_base64(img):
    _, buf = cv2.imencode(".png", img)
    return base64.b64encode(buf).decode("utf-8")


def cv_img_to_rgba(img):
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    img = img.astype(np.float32) / 255.0
    h, w, _ = img.shape
    return w, h, img.flatten()


state = {
    "image_path": None,
    "orig_img": None,
    "binary_img": None,
    "walls": [],
    "texture_tag": "texture_tag",
    "drawlist_tag": "drawlist_tag",
    "areas": [],
    "selecting": None,
    "tmp_pts": [],
}


def process_image(threshold=127, epsilon=2.0, normal_len=10):
    "Run contour extraction and store walls in state."
    if state["orig_img"] is None:
        return

    gray = (
        cv2.cvtColor(state["orig_img"], cv2.COLOR_BGR2GRAY)
        if len(state["orig_img"].shape) == 3
        else state["orig_img"]
    )
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    state["binary_img"] = binary

    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )

    walls = []
    for i, contour in enumerate(contours):
        is_outer = hierarchy[0][i][3] == -1
        approx = cv2.approxPolyDP(contour, epsilon, True)
        for j in range(len(approx)):
            p1 = approx[j][0]
            p2 = approx[(j + 1) % len(approx)][0]
            dx, dy = p2 - p1
            length = np.hypot(dx, dy)
            if length == 0:
                continue
            nx, ny = dy / length, -dx / length

            wall = {
                "x1": int(p1[0]),
                "y1": int(p1[1]),
                "x2": int(p2[0]),
                "y2": int(p2[1]),
                "nx": float(nx),
                "ny": float(ny),
                "outer": bool(is_outer),
            }
            walls.append(wall)
    state["walls"] = walls
    draw_overlays(normal_len)


def draw_overlays(normal_len):
    "Draw stretched image + overlays."
    dpg.delete_item(state["drawlist_tag"], children_only=True)
    dl = state["drawlist_tag"]

    drawlist_width = dpg.get_item_width(dl)
    drawlist_height = dpg.get_item_height(dl)
    dpg.draw_image(
        texture_tag=state["texture_tag"],
        pmin=(0, 0),
        pmax=(drawlist_width, drawlist_height),
        tag="image_widget",
        parent=dl,
    )

    img_h, img_w = state["binary_img"].shape[:2]
    scale_x = drawlist_width / img_w
    scale_y = drawlist_height / img_h

    colors = {"A": (0, 200, 255, 50), "B": (255, 0, 200, 50)}
    border = {"A": (0, 200, 255, 200), "B": (255, 0, 200, 200)}

    for area in state["areas"]:
        pmin = (area["x1"] * scale_x, area["y1"] * scale_y)
        pmax = (area["x2"] * scale_x, area["y2"] * scale_y)
        dpg.draw_rectangle(
            pmin,
            pmax,
            fill=colors[area["name"]],
            color=border[area["name"]],
            thickness=2,
            parent=dl,
        )

    for wall in state["walls"]:
        p1 = (wall["x1"] * scale_x, wall["y1"] * scale_y)
        p2 = (wall["x2"] * scale_x, wall["y2"] * scale_y)
        dpg.draw_line(p1, p2, color=(0, 255, 0, 255), thickness=2, parent=dl)

        mx = (p1[0] + p2[0]) / 2
        my = (p1[1] + p2[1]) / 2
        tip = (mx + wall["nx"] * normal_len, my + wall["ny"] * normal_len)
        dpg.draw_arrow(tip, (mx, my), size=6, color=(255, 0, 0, 255), parent=dl)


def on_image_selected(sender, app_data):
    "Load image, create/replace texture, reset."
    file_path = app_data["file_path_name"]
    img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print("Could not load image:", file_path)
        return
    state["image_path"] = file_path
    state["orig_img"] = img

    w, h, rgba = cv_img_to_rgba(img)
    if dpg.does_item_exist(state["texture_tag"]):
        dpg.delete_item(state["texture_tag"])
    with dpg.texture_registry(show=False):
        dpg.add_raw_texture(
            w, h, rgba, tag=state["texture_tag"], format=dpg.mvFormat_Float_rgba
        )

    state["image_size"] = (w, h)

    epsilon = dpg.get_value("epsilon_slider")
    threshold = dpg.get_value("threshold_slider")
    normal_len = dpg.get_value("normal_len_slider")
    process_image(threshold, epsilon, normal_len)


def on_param_changed(sender, app_data, user_data):
    "Re‑process when sliders change."
    if state["orig_img"] is None:
        return
    epsilon = dpg.get_value("epsilon_slider")
    threshold = dpg.get_value("threshold_slider")
    normal_len = dpg.get_value("normal_len_slider")
    process_image(threshold, epsilon, normal_len)


def on_save(sender, app_data):
    if not state["walls"]:
        print("Nothing to save.")
        return
    save_path = dpg.get_value("save_path_input")
    if not save_path:
        save_path = os.path.splitext(state["image_path"])[0] + ".json"
    if not save_path.endswith(".json"):
        save_path += ".json"

    if os.path.exists(save_path):
        base, ext = os.path.splitext(save_path)
        i = 1
        while os.path.exists(f"{base}_{i}{ext}"):
            i += 1
        save_path = f"{base}_{i}{ext}"

    try:
        walls = state["walls"]

        area_a = next((a for a in state["areas"] if a["name"] == "A"), None)
        area_b = next((a for a in state["areas"] if a["name"] == "B"), None)

        image_data = encode_image_to_base64(state["orig_img"])

        payload = {
            "walls": walls,
            "areas": [area_a, area_b],
            "image": image_data,
        }

        with open(save_path, "w") as f:
            json.dump(payload, f, indent=2)

        print("Saved", save_path)
    except Exception as e:
        print("Save failed:", e)


def open_file_dialog():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff")]
    )
    root.destroy()
    if file_path:
        on_image_selected(None, {"file_path_name": file_path})


def start_area_pick(name):
    state["selecting"] = name
    state["tmp_pts"].clear()


def mouse_to_image_coords(mx, my):
    drawlist_x, drawlist_y = dpg.get_item_rect_min(state["drawlist_tag"])

    rel_x = mx - drawlist_x
    rel_y = my - drawlist_y

    draw_w = dpg.get_item_width(state["drawlist_tag"])
    draw_h = dpg.get_item_height(state["drawlist_tag"])
    img_w, img_h = state["image_size"]
    scale_x, scale_y = img_w / draw_w, img_h / draw_h

    return int(rel_x * scale_x), int(rel_y * scale_y)


def on_mouse_click(sender, app_data):
    if state["selecting"] is None or state["orig_img"] is None:
        return

    mx, my = dpg.get_mouse_pos(local=False)
    ix, iy = mouse_to_image_coords(mx, my)
    state["tmp_pts"].append((ix, iy))

    if len(state["tmp_pts"]) == 2:
        (x1, y1), (x2, y2) = state["tmp_pts"]
        area = {
            "name": state["selecting"],
            "x1": min(x1, x2),
            "y1": min(y1, y2),
            "x2": max(x1, x2),
            "y2": max(y1, y2),
        }
        state["areas"] = [a for a in state["areas"] if a["name"] != area["name"]]
        state["areas"].append(area)

        state["selecting"] = None
        state["tmp_pts"].clear()
        draw_overlays(dpg.get_value("normal_len_slider"))


with dpg.window(label="Wall Extractor", width=1100, height=700, tag="main_window"):
    with dpg.group(horizontal=True):
        dpg.add_button(label="Load Image", callback=open_file_dialog)
        dpg.add_input_text(label="", width=200, tag="save_path_input")
        dpg.add_button(label="Save", callback=on_save)

    with dpg.group(horizontal=False):
        dpg.add_slider_int(
            label="Threshold",
            min_value=0,
            max_value=255,
            default_value=127,
            tag="threshold_slider",
            callback=on_param_changed,
        )
        dpg.add_slider_float(
            label="Epsilon (simplify)",
            min_value=0.5,
            max_value=20,
            default_value=2.0,
            tag="epsilon_slider",
            callback=on_param_changed,
        )
        dpg.add_slider_int(
            label="Normal Length",
            min_value=5,
            max_value=50,
            default_value=10,
            tag="normal_len_slider",
            callback=on_param_changed,
        )
    with dpg.group(horizontal=True):
        dpg.add_button(label="Pick Area A", callback=lambda: start_area_pick("A"))
        dpg.add_button(label="Pick Area B", callback=lambda: start_area_pick("B"))
    with dpg.drawlist(width=512, height=512, tag=state["drawlist_tag"]):
        pass

    with dpg.file_dialog(
        directory_selector=False,
        show=False,
        callback=on_image_selected,
        tag="file_dialog_id",
        width=700,
        height=400,
    ):
        dpg.add_file_extension(".*")
    with dpg.handler_registry():
        dpg.add_mouse_click_handler(callback=on_mouse_click)
dpg.create_viewport(title="Wall Extractor", width=1100, height=700)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("main_window", True)
dpg.start_dearpygui()
dpg.destroy_context()
