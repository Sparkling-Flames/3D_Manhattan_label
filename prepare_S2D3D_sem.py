import os
import json
import glob
import argparse
from PIL import Image
from tqdm import trange
import numpy as np
from shutil import copyfile

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--ori_root', required=True)
parser.add_argument('--new_root', required=True)
args = parser.parse_args()

areas = ['area_1', 'area_2', 'area_3', 'area_4', 'area_5a', 'area_5b', 'area_6']

with open(os.path.join(args.ori_root, 'semantic_labels.json')) as f:
    id2name = [name.split('_')[0] for name in json.load(f)] + ['<UNK>']

with open(os.path.join(args.ori_root, 'name2label.json')) as f:
    name2id = json.load(f)

colors = np.load(os.path.join(args.ori_root, 'colors.npy'))

id2label = np.array([name2id[name] for name in id2name], np.uint8)

for area in areas:
    rgb_paths = sorted(glob.glob(os.path.join(args.ori_root, area, 'pano', 'rgb', '*png')))
    sem_paths = sorted(glob.glob(os.path.join(args.ori_root, area, 'pano', 'semantic', '*png')))
    os.makedirs(os.path.join(args.new_root, area, 'rgb'), exist_ok=True)
    os.makedirs(os.path.join(args.new_root, area, 'semantic'), exist_ok=True)
    os.makedirs(os.path.join(args.new_root, area, 'semantic_visualize'), exist_ok=True)
    for i in trange(len(rgb_paths)):
        rgb_k = os.path.split(rgb_paths[i])[-1]
        sem_k = os.path.split(sem_paths[i])[-1]

        # RGB
        rgb = Image.open(rgb_paths[i]).convert('RGB').resize((1024, 512), Image.LANCZOS)
        rgb.save(os.path.join(args.new_root, area, 'rgb', rgb_k))
        vis = np.array(rgb)
        # Semantic
        sem = np.array(Image.open(sem_paths[i]).resize((1024, 512), Image.NEAREST), np.int32)
        unk = (sem[..., 0] != 0)
        sem = id2label[sem[..., 1] * 256 + sem[..., 2]]
        sem[unk] = 0
        Image.fromarray(sem).save(os.path.join(args.new_root, area, 'semantic', rgb_k))
        # Visualization
        vis = vis // 2 + colors[sem] // 2
        Image.fromarray(vis).save(os.path.join(args.new_root, area, 'semantic_visualize', rgb_k))