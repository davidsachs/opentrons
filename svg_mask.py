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
def image_adjust(proj_targ_x, proj_targ_y):
    global projector, data
    #proj_targ_x = data.get("proj_targ_x")
    #proj_targ_y = data.get("proj_targ_y")
    proj_targ_sx = data.get("proj_targ_sx")
    proj_targ_sy = data.get("proj_targ_sy")
    proj_targ_r = data.get("proj_targ_r")
    proj_adj_x = data.get("proj_adj_x")+300#Good 
    #proj_adj_y = data.get("proj_adj_y")-200# a little to the left
    proj_adj_y = data.get("proj_adj_y")-300#Good

    proj_adj_sx = data.get("proj_adj_sx")
    proj_adj_sy = data.get("proj_adj_sy")
    proj_adj_r = data.get("proj_adj_r")
    image_width = data.get("image_width")
    image_height = data.get("image_height")

    start_x = max(proj_targ_x, 10)
    start_y = max(proj_targ_y, 10)
    
    image_width = 1280.0
    image_height = 960.0

    #end_x = min(proj_targ_x + projector.width, image_width - 10)
    #end_y = min(proj_targ_y + projector.height, image_height - 10)
    end_x = image_width - 10
    end_y = image_height - 10

    # Resize projector according to scale factors
    new_size = (int(projector.width * proj_targ_sx), int(projector.height * proj_targ_sy))
    projector = projector.resize(new_size, Image.LANCZOS)
    
    # Rotate projector around its center by proj_targ_r degrees
    projector = projector.rotate(proj_targ_r, resample=Image.BILINEAR, expand=True)
    # Define ROIs (box tuples in PIL: (left, upper, right, lower))
    image_roi = (start_x, start_y, end_x, end_y)
    proj_roi = (start_x - proj_targ_x, start_y - proj_targ_y, end_x - proj_targ_x, end_y - proj_targ_y)
    #proj_roi = (start_x - proj_targ_x, start_y - proj_targ_y, end_x - start_x, end_y - start_y)
    
    #print(end_x,start_x,end_y,start_y)
    #print(start_x - proj_targ_x, start_y - proj_targ_y, end_x - start_x, end_y - start_y)
    # Crop image ROI
    #image_sub = image.crop(image_roi)

    #print(start_x, proj_targ_x, start_y, proj_targ_y, end_x, end_y, projector.size)
    # Convert projector to grayscale
    proj_adj = projector.convert('L')
    # Crop proj_sub ROI
    proj_sub = projector.crop(proj_roi)
    #print(proj_roi)
    #print("proj_sub", proj_sub.width, proj_sub.height)
    # Clone proj_sub
    projector = proj_sub.copy()

    # Create black output image (1440x2560) in RGB
    proj_output = Image.new('L', (2560, 1440), (0))

    # Resize projector for adjustment scales
    
    new_size_adj = (int(proj_sub.width * proj_adj_sx), int(proj_sub.height * proj_adj_sy))
    print(new_size_adj)
    projector = projector.resize(new_size_adj, Image.LANCZOS)

    # Rotate projector by proj_adj_r degrees around center
    projector = projector.rotate(proj_adj_r, resample=Image.BILINEAR, expand=True)

    # Calculate new start and end coordinates on proj_output
    start_x = max(proj_adj_x, 0)
    start_y = max(proj_adj_y, 0)

    end_x = min(proj_adj_x + projector.width, proj_output.width)
    end_y = min(proj_adj_y + projector.height, proj_output.height)

    output_roi = (start_x, start_y, end_x, end_y)
    proj_roi = (start_x - proj_adj_x, start_y - proj_adj_y, end_x - proj_adj_x, end_y - proj_adj_y)
    #proj_roi = (start_x - proj_adj_x, start_y - proj_adj_y, end_x - start_x, end_y - start_y);

    # Crop the region of projector to paste
    input_sub = projector.crop(proj_roi)

    # Paste input_sub onto proj_output at output_roi upper-left corner
    proj_output.paste(input_sub, (int(start_x), int(start_y)))
    projector = proj_output.copy()
    print("wtf???", projector.size, projector.mode)

# Paths
inkscape_path = r"C:\Program Files\Inkscape\inkscape.com"
projector_path = "C:\\Users\\davidsachs\\Documents\\themachine\\projector\\"
input_svg = projector_path + "proj_ref_video.svg"
output_svg = projector_path + "output.svg"

# Get the SVG namespace
ns = {'svg': 'http://www.w3.org/2000/svg'}
frame = 1
f = open("C:\\Users\\davidsachs\\Downloads\\leopard_move_test_backup\\leopard_move_test\\settings.txt", 'r')
data = json.loads(f.read())
f.close()
#35 50
print(data)
#for height in np.arange(50, 5, -0.75):
for height in np.arange(50, 5, -0.75):
    for side in ["l", "r"]:
        out_file = projector_path + "proj_mask_"+side+"v_" + str(frame) + ".png"
        out_file_np = projector_path + "proj_mask_"+side+"v_" + str(frame) + ".npy"
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
        #os.system("C:\\Program Files\\Inkscape\\inkscape.com output.svg --export-png="+out_file+" -w 4096 -h 4096")
        subprocess.run([
            inkscape_path,
            output_svg,
            "--export-png=" + out_file,  # For Inkscape < 1.0
            "-w", "4096",
            "-h", "4096"
        ])
        projector = Image.open(out_file)
        #"proj_targ_x":-1254.0,"proj_targ_y":-1413.0,
        image_adjust(-1242.0,-1385.0)#Set robot to this. -1242 too far to the left
        #image_adjust(-1200.0,-1000.0)#For some reason send this -800 too far to right
        #image_adjust(-1225.0, -1167.0)
        #if side=='l':
        #    image_adjust(-863, -1386)
        #if side=='r':
        #    image_adjust(-1316, -1386)

        img_array = np.array(projector)
        img_array = np.transpose(img_array)
        np.save(out_file_np, img_array)
        #img = Image.fromarray(img_array, mode='L')  # 'L' for (8-bit pixels, black and white)
        #img.save(out_file)
        
    frame = frame + 1
