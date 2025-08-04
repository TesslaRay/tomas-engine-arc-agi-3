from PIL import Image, ImageDraw


def grid_to_image(grid: list[list[list[int]]], scale_factor: int = 5, show_grid: bool = True) -> Image.Image:
    """Converts a 3D grid of integers into a PIL image, stacking grid layers horizontally.
    
    Args:
        grid: 3D grid of integers representing the game state
        scale_factor: Factor to scale up each pixel (default 5x)
        show_grid: Whether to draw grid lines (default True)
    """
    color_map = [
        (255, 255, 255),
        (0, 0, 170),    
        (153, 153, 153),    
        (102, 102, 102),
        (51, 51, 51),   
        (0, 0, 0),      
        (170, 85, 0),   
        (170, 170, 170),
        (226, 77, 62),  
        (73, 145, 247), 
        (85, 255, 85),  
        (253, 221, 0), 
        (232, 139, 59), 
        (255, 85, 255), 
        (79, 204, 48), 
        (153, 90, 208),  
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

    # Draw grid lines if requested
    if show_grid:
        # Create a semi-transparent overlay for the grid
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        grid_color = (128, 128, 128, 60)  # Semi-transparent gray
        
        for i in range(num_layers):
            offset_x = i * (width * scale_factor + separator_width)
            
            # Draw vertical lines
            for x in range(width + 1):
                line_x = x * scale_factor + offset_x
                if line_x < total_width:
                    draw.line([(line_x, 0), (line_x, height * scale_factor - 1)], fill=grid_color, width=1)
            
            # Draw horizontal lines
            for y in range(height + 1):
                line_y = y * scale_factor
                if line_y < height * scale_factor:
                    draw.line([(offset_x, line_y), (offset_x + width * scale_factor - 1, line_y)], fill=grid_color, width=1)
        
        # Composite the overlay onto the main image
        image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')

    return image 