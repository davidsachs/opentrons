import svgwrite
import subprocess
import numpy as np
# Load the original SVG as a drawing
# svgwrite doesn't directly load existing SVGs, so we'll use xml.etree to read it first
from xml.etree import ElementTree as ET
import json
from PIL import Image
from PIL import ImageStat

data = None
#proj_output = None
projector = None
# Paths
inkscape_path = "C:\\Program Files\\Inkscape\\bin\\inkscape.exe"
projector_path = "C:\\dev\\themachine\\projector\\"
input_svg = projector_path + "Chip_2mm_Hole_no_mask.svg"
output_svg = projector_path + "output.svg"

# Get the SVG namespace
ns = {'svg': 'http://www.w3.org/2000/svg'}
frame = 1
#for height in np.arange(50, 5, -0.75):
for height in np.arange(50, 5, -3):#-0.75):
    for side in ["l", "r"]:
        out_file = projector_path + "proj_mask_"+side+"vs_" + str(frame) + ".png"
        #out_file_np = projector_path + "proj_mask_"+side+"sv_" + str(frame) + ".npy"
        tree = ET.parse(input_svg)
        root = tree.getroot()
        
        # Remove all existing elements (while keeping the <svg> root itself)
        for child in list(root):
            root.remove(child)
        if side=="l":
            y_left = 242+35-height
            rect_l = ET.Element(
                '{http://www.w3.org/2000/svg}rect',
                {
                    'x': '187',  # X coordinate
                    'y': str(y_left),  # Y coordinate
                    'width': '80',
                    'height': str(height),
                    'fill': 'white'
                }
            )
            root.append(rect_l)
        if side=="r":    
            y_right = 177
            rect_r = ET.Element(
                '{http://www.w3.org/2000/svg}rect',
                {
                    'x': '187',  # X coordinate
                    'y': str(y_right),  # Y coordinate
                    'width': '80',
                    'height': str(height),
                    'fill': 'white'
                }
            )
            root.append(rect_r)
        
        # Save modified SVG
        tree.write(output_svg, xml_declaration=True, encoding='utf-8')
        subprocess.run([
            inkscape_path,
            output_svg,
            "--export-type=png",
            "--export-filename=" + out_file,
            "-w", "4096",
            "-h", "4096",
            # Force the background to be black
            "--export-background=#000000", 
            # Force the opacity to be 100% (255 or 1.0 depending on version, 255 is safer for CLI)
            "--export-background-opacity=255" 
        ])
        
    frame = frame + 1
