"""Visible hit-location markers for independently checked farm actions."""
import numpy as np
from smb3_agent.stardew_farm_tasks import require


def verify_farm_marker(image, origin, tile, *, planting=False):
    pixels = np.asarray(image.convert('RGB'))
    r, g, b = pixels[:, :, 0].astype(int), pixels[:, :, 1].astype(int), pixels[:, :, 2].astype(int)
    marker = ((g-r >= 3) & (g-r <= 20) & (r >= 75) & (g <= 200) & (b < 90)) if planting else (
        (r > 140) & (r > 1.8*g) & (g < 110) & (b < 80))

    def matches(tx, ty):
        cx, cy = round(origin[0]+tx*48), round(origin[1]+ty*48)
        for dx in range(-3, 5):
            for dy in range(-3, 5):
                x, y = cx-24+dx, cy-24+dy
                if not (0 <= x and 0 <= y and x+48 <= image.width and y+48 <= image.height):
                    continue
                patch = marker[y:y+48, x:x+48]
                top, bottom = patch[:3].any(axis=0).sum(), patch[-3:].any(axis=0).sum()
                left, right = patch[:,:3].any(axis=1).sum(), patch[:,-3:].any(axis=1).sum()
                edges = [top,bottom,left,right]
                corners = [(top,left,patch[:3,:3]),(top,right,patch[:3,-3:]),
                           (bottom,left,patch[-3:,:3]),(bottom,right,patch[-3:,-3:])]
                located = (sum(e >= 20 for e in edges) >= 3 and max(edges) >= 35) or any(
                    min(a,b) >= 30 and max(a,b) >= 40 and corner.any() for a,b,corner in corners)
                if located and sum(edges) >= 95:
                    return True
        return False
    found = {(tile[0]+dx,tile[1]+dy) for dx in (-1,0,1) for dy in (-1,0,1)
             if matches(tile[0]+dx,tile[1]+dy)}
    require(found == {tile}, 'visible farm marker does not uniquely match the reviewed target')
