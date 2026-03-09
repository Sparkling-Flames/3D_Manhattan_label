"""
Visualize HoHoNet layout predictions overlaid on the original panorama image.
Draws corner points, ceiling/floor boundaries, and wall corner lines.
"""
import os
import argparse
import numpy as np
from PIL import Image, ImageDraw


def draw_boundaries(img, bon, color=(0, 255, 0), width=2):
    """Draw ceiling and floor boundary lines"""
    draw = ImageDraw.Draw(img)
    W = img.width
    
    # Ceiling boundary
    ceil_pts = [(x, int(bon[0, x])) for x in range(W)]
    draw.line(ceil_pts, fill=color, width=width)
    
    # Floor boundary
    floor_pts = [(x, int(bon[1, x])) for x in range(W)]
    draw.line(floor_pts, fill=color, width=width)
    
    return img


def draw_corners(img, cor_id, color=(255, 0, 0), radius=5, line_width=3):
    """Draw corner points and vertical lines between ceiling-floor pairs"""
    draw = ImageDraw.Draw(img)
    
    # Draw vertical lines for each corner
    for i in range(0, len(cor_id), 2):
        ceil_pt = tuple(cor_id[i].astype(int))
        floor_pt = tuple(cor_id[i+1].astype(int))
        
        # Draw vertical line
        draw.line([ceil_pt, floor_pt], fill=color, width=line_width)
        
        # Draw corner points
        draw.ellipse([ceil_pt[0]-radius, ceil_pt[1]-radius, 
                      ceil_pt[0]+radius, ceil_pt[1]+radius], 
                     fill=color, outline=(255, 255, 255))
        draw.ellipse([floor_pt[0]-radius, floor_pt[1]-radius, 
                      floor_pt[0]+radius, floor_pt[1]+radius], 
                     fill=color, outline=(255, 255, 255))
    
    return img


def draw_layout_on_image(img_path, layout_path, output_path=None, 
                         show_boundaries=True, show_corners=True):
    """
    Overlay layout prediction on panorama image
    
    Args:
        img_path: Path to original panorama image
        layout_path: Path to .layout.txt (corner coordinates)
        output_path: Where to save the result (None = display only)
        show_boundaries: Whether to draw ceiling/floor boundaries
        show_corners: Whether to draw corner lines and points
    """
    # Load image
    img = Image.open(img_path).convert('RGB')
    W, H = img.size
    
    # Load corner coordinates
    with open(layout_path) as f:
        cor_id = np.array([line.strip().split() for line in f], np.float32)
    
    # Generate boundary signal from corners (simplified version)
    if show_boundaries:
        bon = np.zeros((2, W))
        # Interpolate ceiling boundary
        ceil_pts = cor_id[::2]  # Even rows = ceiling
        ceil_x = ceil_pts[:, 0]
        ceil_y = ceil_pts[:, 1]
        bon[0] = np.interp(np.arange(W), ceil_x, ceil_y, period=W)
        
        # Interpolate floor boundary
        floor_pts = cor_id[1::2]  # Odd rows = floor
        floor_x = floor_pts[:, 0]
        floor_y = floor_pts[:, 1]
        bon[1] = np.interp(np.arange(W), floor_x, floor_y, period=W)
        
        img = draw_boundaries(img, bon, color=(0, 255, 0), width=2)
    
    # Draw corner lines and points
    if show_corners:
        img = draw_corners(img, cor_id, color=(255, 0, 0), radius=6, line_width=3)
    
    # Save or show
    if output_path:
        img.save(output_path)
        print(f'Saved to {output_path}')
    else:
        img.show()
    
    return img


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Visualize layout predictions on 2D panorama images',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--img', required=True,
                        help='Path to input panorama image')
    parser.add_argument('--layout', required=True,
                        help='Path to layout prediction (.layout.txt or .txt)')
    parser.add_argument('--out', default=None,
                        help='Output image path (if not set, will display)')
    parser.add_argument('--no_boundaries', action='store_true',
                        help='Hide ceiling/floor boundary lines')
    parser.add_argument('--no_corners', action='store_true',
                        help='Hide corner points and vertical lines')
    args = parser.parse_args()
    
    # Auto-generate output path if not specified
    if args.out is None and not args.no_boundaries and not args.no_corners:
        base = os.path.splitext(args.img)[0]
        args.out = f'{base}_layout_overlay.png'
    
    draw_layout_on_image(
        args.img, 
        args.layout, 
        args.out,
        show_boundaries=not args.no_boundaries,
        show_corners=not args.no_corners
    )
