from PIL import Image


def grid_to_image(grid: list[list[list[int]]]) -> Image.Image:
    """Converts a 3D grid of integers into a PIL image, stacking grid layers horizontally."""
    color_map = [
        (255, 255, 255),# 0: Negro
        (0, 0, 170),    # 1: Azul oscuro
        (0, 170, 0),    # 2: Verde oscuro
        (102, 102, 102),# 3: Gris oscuro (0x666666)
        (51, 51, 51),   # 4: Gris claro (0x333333)
        (0, 0, 0),      # 5: Negro
        (170, 85, 0),   # 6: Marrón
        (170, 170, 170),# 7: Gris claro
        (226, 77, 62),  # 8: Rojo medio
        (73, 145, 247), # 9: Azul claro (0x4991F7)
        (85, 255, 85),  # 10: Verde claro
        (85, 255, 255), # 11: Cian claro
        (232, 139, 59), # 12: Naranja (0xe88b3b)
        (255, 85, 255), # 13: Magenta claro
        (255, 255, 85), # 14: Amarillo
        (153, 90, 208), # 15: Morado
    ]

    if not grid or not grid[0]:
        # Create empty image if grid is empty
        return Image.new("RGB", (200, 200), color="black")

    height = len(grid[0])
    width = len(grid[0][0])
    num_layers = len(grid)

    # Add a small separator between grids if there are multiple layers
    separator_width = 5 if num_layers > 1 else 0
    total_width = (width * num_layers) + (separator_width * (num_layers - 1))

    image = Image.new("RGB", (total_width, height), "white")
    pixels = image.load()

    for i, grid_layer in enumerate(grid):
        # Check if grid_layer is valid
        if len(grid_layer) != height or len(grid_layer[0]) != width:
            continue

        offset_x = i * (width + separator_width)
        for y in range(height):
            for x in range(width):
                color_index = grid_layer[y][x] % 16
                pixels[x + offset_x, y] = color_map[color_index]

    return image 