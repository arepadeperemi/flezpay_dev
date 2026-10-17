import math

RETAIL_COLORS = {
    "Black": "#000000",
    "White": "#FFFFFF",
    "Gray": "#808080",
    "Silver": "#C0C0C0",
    "Red": "#FF0000",
    "Burgundy": "#800020",
    "Maroon": "#800000",
    "Pink": "#FFC0CB",
    "Rose": "#FF007F",
    "Orange": "#FFA500",
    "Peach": "#FFE5B4",
    "Yellow": "#FFFF00",
    "Gold": "#FFD700",
    "Brown": "#A52A2A",
    "Beige": "#F5F5DC",
    "Khaki": "#F0E68C",
    "Green": "#008000",
    "Olive": "#808000",
    "Lime": "#00FF00",
    "Mint": "#98FF98",
    "Teal": "#008080",
    "Cyan": "#00FFFF",
    "Blue": "#0000FF",
    "Navy": "#000080",
    "Sky Blue": "#87CEEB",
    "Royal Blue": "#4169E1",
    "Purple": "#800080",
    "Violet": "#EE82EE",
    "Lavender": "#E6E6FA",
    "Indigo": "#4B0082",
    "Cream": "#FFFDD0",
    "Ivory": "#FFFFF0",
    "Charcoal": "#36454F",
    "Transparent": "#FFFFFF", # Hard to map mathematically, fallback to White or transparent handling
}

def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    if len(hex_code) != 6:
        return (255, 255, 255)
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def get_closest_color_name(hex_value):
    if not hex_value or not hex_value.startswith('#'):
        return None
        
    target_rgb = hex_to_rgb(hex_value)
    
    min_distance = float('inf')
    closest_name = "Unknown"
    
    for name, code in RETAIL_COLORS.items():
        if name == "Transparent":
            continue
            
        color_rgb = hex_to_rgb(code)
        
        # Euclidean distance
        dist = math.sqrt(
            (target_rgb[0] - color_rgb[0]) ** 2 +
            (target_rgb[1] - color_rgb[1]) ** 2 +
            (target_rgb[2] - color_rgb[2]) ** 2
        )
        
        if dist < min_distance:
            min_distance = dist
            closest_name = name
            
    return closest_name
