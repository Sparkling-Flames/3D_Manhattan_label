"""Composite Blender 8-bit RGBA PNG over white using only Python's stdlib."""
import argparse,struct,zlib
from pathlib import Path

def chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)

def read_rgba(path):
    raw=Path(path).read_bytes()
    if raw[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Not PNG')
    offset=8;chunks=[];compressed=b''
    while offset<len(raw):
        n=struct.unpack('>I',raw[offset:offset+4])[0];kind=raw[offset+4:offset+8];data=raw[offset+8:offset+8+n];offset+=12+n
        if kind==b'IHDR':w,h,depth,color,compress,filt,interlace=struct.unpack('>IIBBBBB',data)
        elif kind==b'IDAT':compressed+=data
        elif kind in {b'gAMA',b'cHRM',b'sRGB',b'iCCP',b'pHYs'}:chunks.append((kind,data))
    if (depth,color,compress,filt,interlace)!=(8,6,0,0,0):raise ValueError('Expected noninterlaced 8-bit RGBA PNG')
    raw=zlib.decompress(compressed);stride=w*4;previous=bytearray(stride);rows=[]
    for y in range(h):
        mode=raw[y*(stride+1)];row=bytearray(raw[y*(stride+1)+1:(y+1)*(stride+1)])
        for x in range(stride):
            left=row[x-4] if x>=4 else 0;up=previous[x];ul=previous[x-4] if x>=4 else 0
            if mode==0:predict=0
            elif mode==1:predict=left
            elif mode==2:predict=up
            elif mode==3:predict=(left+up)//2
            elif mode==4:
                p=left+up-ul;da,db,dc=abs(p-left),abs(p-up),abs(p-ul)
                predict=left if da<=db and da<=dc else up if db<=dc else ul
            else:raise ValueError('Unknown PNG filter')
            row[x]=(row[x]+predict)&255
        rows.append(row);previous=row
    return w,h,rows,chunks

def composite(source,target):
    w,h,rows,metadata=read_rgba(source);pixels=bytearray()
    for row in rows:
        pixels.append(0)
        for x in range(0,len(row),4):
            a=row[x+3]
            pixels.extend((row[x+c]*a+255*(255-a)+127)//255 for c in range(3))
    out=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))
    for kind,data in metadata:out+=chunk(kind,data)
    out+=chunk(b'IDAT',zlib.compress(pixels,6))+chunk(b'IEND',b'')
    Path(target).write_bytes(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('target',type=Path);a=p.parse_args();composite(a.source,a.target)
