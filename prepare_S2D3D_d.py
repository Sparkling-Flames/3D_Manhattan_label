import os
import glob
import argparse
from tqdm import tqdm

import numpy as np
import imageio.v2 as imageio
from skimage.transform import rescale

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--ori_root', required=True)
parser.add_argument('--new_root', required=True)
args = parser.parse_args()

areas = ['area_1', 'area_2', 'area_3', 'area_4', 'area_5a', 'area_5b', 'area_6']

for area in areas:
    print('Processing:', area)
    os.makedirs(os.path.join(args.new_root, area, 'rgb'), exist_ok=True)
    os.makedirs(os.path.join(args.new_root, area, 'depth'), exist_ok=True)
    for fname in tqdm(os.listdir(os.path.join(args.ori_root, area, 'pano', 'rgb'))):
        if fname[0] == '.' or not fname.endswith('png'):
            continue
        rgb_path = os.path.join(args.ori_root, area, 'pano', 'rgb', fname)
        d_path = os.path.join(args.ori_root, area, 'pano', 'depth', fname[:-7] + 'depth.png')
        assert os.path.isfile(d_path)

        rgb = imageio.imread(rgb_path)[..., :3]
        depth = imageio.imread(d_path)
        rgb = rescale(rgb, 0.25, order=0, mode='wrap', anti_aliasing=False, preserve_range=True, channel_axis=-1)
        depth = rescale(depth, 0.25, order=0, mode='wrap', anti_aliasing=False, preserve_range=True)

        imageio.imwrite(os.path.join(args.new_root, area, 'rgb', fname), rgb.astype(np.uint8))
        imageio.imwrite(os.path.join(args.new_root, area, 'depth', fname[:-7] + 'depth.png'), depth.astype(np.uint16))