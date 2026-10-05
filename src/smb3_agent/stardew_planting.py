"""Passive, frame-bound planting discussion. Never creates gameplay authority."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image
import numpy as np

from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_farm_perception import patch_matches, stable_patch
from smb3_agent.stardew_perception import pixel_digest

# Normal outdoor growth, daily watering, no fertilizer/profession bonuses.
# Sources checked 2026-10-04; rules are distinct from screen observations.
CROP_RULES = {
    'corn': {'seasons': ['summer', 'fall'], 'days': 14, 'trellis': False},
    'tomato': {'seasons': ['summer'], 'days': 11, 'trellis': False},
    'parsnip': {'seasons': ['spring'], 'days': 4, 'trellis': False},
    'green bean': {'seasons': ['spring'], 'days': 10, 'trellis': True},
}
RULE_SOURCE = 'https://stardewvalleywiki.com/Crops'


def crop_in(text):
    value = text.lower()
    value = re.split(r"\b(?:instead of|rather than)\b", value)[0]
    found = []
    for pattern, crop in [(r'green beans?|beans?', 'green bean'), (r'corn', 'corn'),
                          (r'tomatoes|tomatos|tomato', 'tomato'), (r'parsnips?', 'parsnip')]:
        found.extend((match.start(), crop) for match in re.finditer(r'\b(?:' + pattern + r')\b', value))
    return max(found)[1] if found else None


def requested_crop(text, previous=None):
    known = crop_in(text)
    if known:
        return known
    match = re.search(r"\b(?:plant|grow|sow|how about|what about|switch to|change to|actually|prefer|try)\s+(?:some\s+)?([a-z]+)(?:\s+seeds)?\b", text.lower())
    if match and match[1] not in {'a','the','this','that','there','here','it','them','another','where','crop','crops'}:
        return match[1]
    return (previous or {}).get('crop')


def location_request(text, previous=None):
    value = text.lower().strip(' ?.!,')
    if re.search(r'\b(?:water|harvest|clear|stop|pause)\b', value) and not re.search(r'\b(?:where|spot|location)\b', value):
        return False
    initial = bool(re.search(r'\b(?:where|spot|location|place|area)\b', value)
                   and re.search(r'\b(?:plant|grow|sow|crop)\b', value))
    followup = bool(previous and (crop_in(value) or re.search(
        r'\b(?:why|instead|other|another|closer|farther|left|right|north|south|east|west|mailbox|porch|pond|tree|patch|below|above|near|there|here|prefer|how about|what about|change|choose|that spot|this spot|suitable)\b', value)))
    return initial or followup


class PlantingSurvey:
    """Bounded whole-tile raster matches against retained real-farm frames.

    Missing/changed tiles stay unknown. The calibration supplies labels, never
    current emptiness. Access strips are always reserved, including for trellises.
    """
    def __init__(self, profile, manifest=Path('data/stardew-planting-survey.json')):
        self.profile = profile
        config = json.loads(Path(manifest).read_text())
        self.config = next((p for p in config['profiles'] if p['profile_id'] == profile.profile_id), None)
        if self.config is None:
            raise StardewAdapterError('This farm has no planting survey calibration.')

    def inspect(self, screenshot, *, session_id, observed_at=None, inspection=False):
        config = self.config
        path = Path(config['image'])
        if not self.profile.qualified() or hashlib.sha256(path.read_bytes()).hexdigest() != config['sha256']:
            raise StardewAdapterError('Planting survey calibration evidence changed; reconnect the supported farm.')
        with Image.open(path) as source:
            reference = source.convert('RGB')
        with Image.open(screenshot) as source:
            image = source.convert('RGB')
        variants = [(reference, config['origin'])]
        for variant in config.get('variants', []):
            path = Path(variant['image'])
            if hashlib.sha256(path.read_bytes()).hexdigest() != variant['sha256']:
                raise StardewAdapterError('Planting survey variant evidence changed.')
            with Image.open(path) as source:
                variants.append((source.convert('RGB'), variant['origin']))
        origins, _, player, uncertainty = self.profile.geometry(image)
        targets = []
        for spec in config['targets'] + (config.get('inspection_targets', []) if inspection else []):
            boxes = [tuple(round(v + origin[i % 2] - config['origin'][i % 2])
                           for i, v in enumerate(spec['box'])) for origin in origins]
            matches = []
            for raster, variant_origin in variants:
                reference_box = tuple(round(v + variant_origin[i % 2] - config['origin'][i % 2])
                                      for i, v in enumerate(spec['box']))
                sample = stable_patch(raster.crop(reference_box))
                matches.extend(box for box in boxes if 0 <= box[0] < box[2] <= image.width
                    and 0 <= box[1] < box[3] <= min(image.height, 840)
                    and patch_matches(stable_patch(image.crop(box)), sample)
                    # Keep tiny seeds/obstacles visible: variants change the
                    # observed baseline, never relax this whole-pixel bound.
                    and int(np.abs(np.asarray(image.crop(box), dtype=np.int16)
                                   - np.asarray(raster.crop(reference_box), dtype=np.int16)).max()) <= 16)
            x, y = spec['tile']
            # The avatar/cursor can hide a local change; do not certify its tile.
            hidden = abs(x*48-player[0]) <= 32+uncertainty and -80 <= y*48-player[1] <= 28
            state = spec['state'] if matches and not hidden else 'unknown'
            targets.append({**spec, 'state': state, 'box': list(matches[0] if matches else boxes[0])})
        calendar = {}
        for key in ('season', 'day'):
            box = config[key+'_box']
            calendar[key] = config[key] if pixel_digest(image.crop(box)) == pixel_digest(reference.crop(box)) else None
        traversable = {tuple(t['tile']) for t in targets if t['state'] in ('access', 'empty_dirt')}
        entry = (1, 2)  # Visibly clear ground adjoining the supported porch.
        for target in targets:
            tile = tuple(target['tile'])
            reachable = {entry} if entry in traversable and entry != tile else set()
            pending = list(reachable)
            for x, y in pending:
                for neighbor in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                    if neighbor in traversable and neighbor != tile and neighbor not in reachable:
                        reachable.add(neighbor)
                        pending.append(neighbor)
            target['access_observed'] = any(abs(tile[0]-x)+abs(tile[1]-y) == 1 for x,y in reachable)
        # Browser visual evidence is the exact captured scene, not a conceptual map.
        output = io.BytesIO()
        image.save(output, format='PNG')
        return {'observation_id': uuid4().hex, 'session_id': session_id,
                'observed_at': observed_at or datetime.now(timezone.utc).isoformat(),
                'profile_id': self.profile.profile_id, 'targets': targets, **calendar,
                'screenshot': str(screenshot), 'image_sha256': hashlib.sha256(Path(screenshot).read_bytes()).hexdigest(),
                'image': 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode(),
                'width': image.width, 'height': image.height, 'input_emitted': False}


def recommend(text, observation, previous=None):
    crop = requested_crop(text, previous)
    rule = CROP_RULES.get(crop)
    reasons = []
    season, day = observation.get('season'), observation.get('day')
    fresh = False
    try:
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(observation['observed_at'])).total_seconds()
        fresh = 0 <= age <= 5 and bool(observation.get('session_id')) and bool(observation.get('observation_id'))
    except (KeyError, ValueError, TypeError):
        pass
    if not fresh:
        season, day = None, None
        reasons.append('A fresh farm inspection is needed; saved or stale views cannot establish current suitability.')
    season_status = 'unknown'
    if rule and season in ('spring','summer','fall','winter') and type(day) is int and 1 <= day <= 28:
        # Corn continues growing across summer -> fall; no other rule here does.
        days_left = 28-day + (28 if crop == 'corn' and season == 'summer' else 0)
        if season not in rule['seasons']:
            season_status = 'unsuitable'
            reasons.append(f'{crop.capitalize()} grows outdoors in {" or ".join(rule["seasons"])}; the observed farm is in {season}, day {day}.')
        elif rule['days'] > days_left:
            season_status = 'unsuitable'
            reasons.append(f'{crop.capitalize()} needs {rule["days"]} growing days; only {days_left} remain before its season ends, assuming daily watering and no growth bonuses.')
        else:
            season_status = 'suitable'
            reasons.append(f'{crop.capitalize()} fits {season}, day {day}: {rule["days"]} days to first harvest with daily watering and no growth bonuses.')
    elif rule:
        reasons.append('The current season or day is not clearly observed; timing suitability is unknown.')
    else:
        reasons.append('Which crop would you like to grow? I have outdoor rules for corn, tomato, parsnip and green bean; other crops need verified rules before a recommendation.')
    assessments = []
    for target in observation.get('targets', []):
        state = target.get('state')
        status, why = 'insufficiently_observed', 'Terrain, occupancy or access needs a clear current view.'
        if fresh and state in ('occupied','protected','access','debris'):
            status, why = 'unsuitable', {'occupied':'Existing crops must be preserved.', 'protected':'Protected vegetation must be preserved.', 'access':'Keep this access strip clear.', 'debris':'Occupied by debris; clearing is a separate activity.'}[state]
        elif fresh and state == 'empty_dirt' and target.get('access_observed'):
            status = 'suitable' if season_status == 'suitable' else 'unsuitable' if season_status == 'unsuitable' else 'insufficiently_observed'
            why = 'Observed empty dirt with an adjacent reserved access strip; tilling would be needed in a later activity.'
            if season_status != 'suitable':
                why += ' Crop timing is ' + season_status + '.'
        assessments.append({**target, 'suitability': status, 'reason': why})
    spatial = [t for t in assessments if fresh and t.get('state') == 'empty_dirt' and t.get('access_observed')]
    preference = (previous or {}).get('preference', '')
    value = text.lower()
    if re.search(r'\b(?:other|another)\b', value):
        old = (previous or {}).get('location_id')
        spatial = [t for t in spatial if t['id'] != old]
        preference = 'another spot'
    elif re.search(r'\b(?:mailbox|right|farther)\b', value):
        spatial.sort(key=lambda t: t['tile'][0], reverse=True)
        preference = 'near the mailbox'
    elif re.search(r'\b(?:left|closer|crops)\b', value):
        spatial.sort(key=lambda t: t['tile'][0])
        preference = 'near the starter crops'
    elif previous and preference == 'near the mailbox':
        spatial.sort(key=lambda t: t['tile'][0], reverse=True)
    elif previous and preference == 'another spot':
        spatial.sort(key=lambda t: t['id'] != previous.get('location_id'))
    requested = [t for t in assessments if t['label'].lower() in value]
    if 'porch' in value:
        requested = [t for t in assessments if t.get('state') == 'access']
    if re.search(r'\b(?:on|in) (?:the )?(?:existing |starter )?crop(?:s| patch)?\b', value):
        requested = [t for t in assessments if t.get('state') == 'occupied']
    if re.search(r'\b(?:pond|cave|north of|south of|west of|left of (?:the )?(?:house|farmhouse)|above (?:the )?(?:house|porch))\b', value):
        reasons.append('That requested area is outside the observed candidate/access survey; its suitability is insufficiently observed.')
        spatial = []
    if requested and requested[0] in spatial:
        spatial.sort(key=lambda t: t['id'] != requested[0]['id'])
        preference = 'near the mailbox' if 'mailbox' in requested[0]['label'] else 'near the starter crops'
    if requested and requested[0]['suitability'] != 'suitable':
        reasons.append(f'The requested {requested[0]["label"]}: {requested[0]["reason"]}')
    selected = spatial[0] if spatial and rule else None
    if selected:
        prefix = 'For a future seasonal plan, consider' if season_status == 'unsuitable' else 'I recommend' if season_status == 'suitable' else 'A possible location, pending the calendar check, is'
        reasons.append(f'{prefix} the {selected["label"]} (outlined in the farm view). {selected["reason"]}')
        if rule['trellis']:
            reasons.append('Green beans use a trellis that blocks walking. Use this single outer tile, leaving the adjacent access strip open; no larger trellis layout is assessed.')
    else:
        reasons.append('No suitable empty location is confirmed in this view. Show the supported farm from the porch and ask again; unseen locations need separate inspection. No movement has been authorized.')
    if season_status == 'unsuitable':
        alternatives = [name for name,r in CROP_RULES.items() if season in r['seasons'] and type(day) is int and r['days'] <= 28-day]
        reasons.append(('For this season, consider ' + ' or '.join(alternatives) + ' instead; ask me to compare a spot for that crop.') if alternatives else 'Plan for the next supported growing season and recheck the farm then.')
    reasons.append('Seeds, tools, water supply and energy have not been inspected. This chooses a location only; planting, tilling, clearing and buying need separate activities and approval.')
    return {'recommendation_id': uuid4().hex, 'crop': crop, 'preference': preference,
            'location_id': selected['id'] if selected else None,
            'status': season_status if fresh and selected and season_status != 'unknown' else 'insufficiently_observed',
            'message': ' '.join(reasons), 'assessments': assessments,
            'observation': observation, 'crop_rule': rule, 'rule_source': RULE_SOURCE,
            'authorization_granted': False, 'historical': False}
