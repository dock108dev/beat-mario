"""Route-specific sprite recognition from reviewed native foliage captures.

Camera position and movement history never supply a player location. Sparse
pants and boot features must agree on a unique bounded translation. Calibration
is retained in the route evidence; unknown lighting/occlusion refuses movement.
"""
from functools import lru_cache

import numpy as np
from PIL import Image

from smb3_agent.stardew_adapter import StardewAdapterError


def sprite_features(image, foot):
    pixels = np.asarray(image, dtype=np.int16)
    x, y = map(round, foot)
    if not 20 <= x < image.width-21 or not 34 <= y < min(826, image.height-14):
        raise StardewAdapterError('Cave avatar calibration is outside the viewport.')
    patch = pixels[y-34:y+14, x-20:x+21]
    r, g, b = patch.transpose(2, 0, 1)
    blue = (b-r > 45) & (b-g > 25) & (b > 90)
    boots = (r-g > 3) & (g-b > 8) & (r < 110) & (b < 40)
    boots[:30] = False
    if blue.sum() < 16 or boots.sum() < 12:
        raise StardewAdapterError('Cave avatar calibration lacks separate pants and boots.')
    yy, xx = np.where(blue | boots)
    return np.array([xx-20, yy-34]).T, patch[yy, xx], blue[yy, xx]


@lru_cache(maxsize=8)
def _templates(references):
    bank = []
    for path, x, y in references:
        with Image.open(path) as im:
            feature = sprite_features(im.convert('RGB'), (x, y))
        if not any(all(np.array_equal(a, b) for a, b in zip(feature, old)) for old in bank):
            bank.append(feature)
    return bank


def locate_avatar(image, references):
    """Return current foot center and raster interval; never last-known position."""
    pixels = np.asarray(image, dtype=np.int16)
    r, g, b = pixels[:840].transpose(2, 0, 1)
    yy, xx = np.where((b-r > 45) & (b-g > 25) & (b > 90))
    points = set(zip(yy, xx))
    candidates = []
    while points:
        component = [points.pop()]
        index = 0
        while index < len(component):
            y, x = component[index]
            index += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    p = (y+dy, x+dx)
                    if p in points:
                        points.remove(p)
                        component.append(p)
        ys, xs = np.array(component).T
        if len(component) < 12 or np.ptp(xs) > 40 or np.ptp(ys) > 36:
            continue
        center = int((xs.min()+xs.max())/2)
        candidates.extend((x, y) for x in range(center-12, center+13)
                          for y in range(int(ys.max())+2, int(ys.max())+29))
    if not candidates:
        raise StardewAdapterError('Cave player is hidden or unrecognized.')
    candidates = np.unique(np.array(candidates), axis=0)
    candidates = candidates[(candidates[:, 0] > 20) & (candidates[:, 0] < image.width-21)
                            & (candidates[:, 1] > 34) & (candidates[:, 1] < min(826, image.height-14))]
    scores = np.zeros(len(candidates))
    refs = tuple((p['image'], *p['foot_reference']) for p in references)
    for delta, colors, blue in _templates(refs):
        groups = [np.flatnonzero(blue), np.flatnonzero(~blue)]
        probes = np.concatenate([g[np.linspace(0, len(g)-1, 8, dtype=int)] for g in groups])
        d = delta[probes]
        sample = pixels[candidates[:, 1, None]+d[None, :, 1], candidates[:, 0, None]+d[None, :, 0]]
        coarse = np.max(abs(sample-colors[probes]), axis=2) <= 18
        selected = np.flatnonzero((coarse[:, :8].mean(axis=1) >= .5)
                                  & (coarse[:, 8:].mean(axis=1) >= .5)
                                  & (coarse.mean(axis=1) >= .7))
        for start in range(0, len(selected), 512):
            indices = selected[start:start+512]
            c = candidates[indices]
            sample = pixels[c[:, 1, None]+delta[None, :, 1], c[:, 0, None]+delta[None, :, 0]]
            match = np.max(abs(sample-colors), axis=2) <= 18
            pants = match[:, blue].mean(axis=1)
            boots = match[:, ~blue].mean(axis=1)
            score = np.where((pants >= .65) & (boots >= .65), (pants+boots)/2, 0)
            scores[indices] = np.maximum(scores[indices], score)
    if not len(scores) or scores.max() < .90:
        raise StardewAdapterError('Cave player is hidden or unrecognized.')
    accepted = candidates[scores >= scores.max()-.035]
    spread = np.ptp(accepted, axis=0)
    if spread.max() > 3:
        raise StardewAdapterError('Cave player location is ambiguous.')
    center = (accepted.min(axis=0)+accepted.max(axis=0))/2
    return tuple(map(float, center)), max(1.5, float(spread.max())/2+.5)
