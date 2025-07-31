from PIL import Image


def grid_to_image(grid: list[list[list[int]]], scale_factor: int = 5) -> Image.Image:
    """Converts a 3D grid of integers into a PIL image, stacking grid layers horizontally.
    
    Args:
        grid: 3D grid of integers representing the game state
        scale_factor: Factor to scale up each pixel (default 5x)
    """
    color_map = [
        (255, 255, 255),# 1: Negro
        (0, 0, 170),    # 2: Azul oscuro
        (0, 170, 0),    # 3: Verde oscuro
        (102, 102, 102),# 4: Gris oscuro 
        (51, 51, 51),   # 5: Gris claro 
        (0, 0, 0),      # 6: Negro
        (170, 85, 0),   # 7: Marrón
        (170, 170, 170),# 8: Gris claro
        (226, 77, 62),  # 9: Rojo medio
        (73, 145, 247), # 10: Azul claro 
        (85, 255, 85),  # 11: Verde claro
        (85, 255, 255), # 12: Cian claro
        (232, 139, 59), # 13: Naranja 
        (255, 85, 255), # 14: Magenta claro
        (255, 255, 85), # 15: Amarillo
        (153, 90, 208), # 16: Morado
    ]

    if not grid or not grid[0]:
        # Create empty image if grid is empty
        return Image.new("RGB", (200 * scale_factor, 200 * scale_factor), color="black")

    height = len(grid[0])
    width = len(grid[0][0])
    num_layers = len(grid)

    # Add a small separator between grids if there are multiple layers
    separator_width = 5 * scale_factor if num_layers > 1 else 0
    total_width = (width * num_layers * scale_factor) + (separator_width * (num_layers - 1))

    image = Image.new("RGB", (total_width, height * scale_factor), "white")
    pixels = image.load()

    for i, grid_layer in enumerate(grid):
        # Check if grid_layer is valid
        if len(grid_layer) != height or len(grid_layer[0]) != width:
            continue

        offset_x = i * (width * scale_factor + separator_width)
        for y in range(height):
            for x in range(width):
                color_index = grid_layer[y][x] % 16
                color = color_map[color_index]
                
                # Fill a scale_factor x scale_factor block with the same color
                for dy in range(scale_factor):
                    for dx in range(scale_factor):
                        pixel_x = x * scale_factor + dx + offset_x
                        pixel_y = y * scale_factor + dy
                        if pixel_x < total_width and pixel_y < height * scale_factor:
                            pixels[pixel_x, pixel_y] = color

    return image 