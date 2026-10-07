"""Bounded visible display normalization, independent of farm/save arrangement."""
from pathlib import Path
import hashlib
import json
from uuid import uuid4

import numpy as np
from PIL import Image

from smb3_agent.paths import repository_path
from smb3_agent.stardew_adapter import StardewAdapterError, InputCommand, InputKind
from smb3_agent.stardew_perception import CameraAlignment, MaskedPixelTemplate
from smb3_agent.candidate_resources import resolve_resource_values

SOURCE_PROFILE = 'artifacts/gc-delivery/ordinary-session/20261006-recovery/view-feature-calibration/profile.json'
PACKAGED_PROFILE = 'data/calibration/view-settings/profile.json'


class ViewSettingFeatures:
    def __init__(self, manifest=None):
        manifest = Path(manifest) if manifest else repository_path(PACKAGED_PROFILE)
        if not manifest.is_file():
            manifest = repository_path(SOURCE_PROFILE)
        self.config = resolve_resource_values(json.loads(manifest.read_text()))
        if self.config.get('schema') != 'stardew-view-setting-features/v1':
            raise StardewAdapterError('Visible display control recognition unavailable')
        for name, digest in self.config['evidence_hashes'].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
                raise StardewAdapterError('Visible display feature evidence changed')
        self.images = {name: Image.open(path).convert('RGBA') for name, path in self.config['features'].items()}
        self.alignments = {name: CameraAlignment(MaskedPixelTemplate.from_image(image, True), 0)
                           for name, image in self.images.items()}
        self.ink = tuple(self.config['ink'])

    def locate(self, image, name, box):
        crop = image.crop(box)
        try:
            points = self.alignments[name].offsets(crop)
        except StardewAdapterError:
            return None
        if len(points) != 1:
            return None
        x, y = points[0]
        return x+box[0], y+box[1]

    def percentage(self, image, label):
        x, y = label
        actual = np.all(np.asarray(image.crop((x-155,y,x-50,y+41))) == self.ink, axis=2)
        matches = [value for value in range(75,101,5)
                   if np.array_equal(actual, np.asarray(self.images[f'percent-{value}'])[:,:,3] > 0)]
        if len(matches) != 1:
            raise StardewAdapterError('The current display percentage is not independently recognized')
        return matches[0]


def normalize_view(native, driver, *, isolation, authority, root, cancel, result, tool_marker=False, marker_only=False):
    """Only Escape, the identified Options tab, scrollbar and Zoom minus.

    No save parsing/writes, world routes or inferred resource values. Every
    widget action is followed by a new capture; failed effects consume the
    finite budget and stop. Farm readiness is checked separately afterward.
    """
    features = ViewSettingFeatures()
    steps = result.setdefault('view_setting_steps', [])
    def observe():
        authority()
        window = native.detect_window()
        isolation(window)
        if window.bounds != (0,33,1512,949):
            raise StardewAdapterError('Display preparation needs the complete supported viewport')
        path = native.capture(window, root/f'view-settings-{uuid4().hex}.png')
        authority()
        return window, path, Image.open(path).convert('RGB')
    def record(path, action, **values):
        result['reason'] = {'open_menu': 'Preparing the isolated game view.', 'options_tab': 'Opening visible view settings.', 'tool_hit_changed': 'Adjusting the visible tool target marker in this isolated copy.', 'tool_hit_ready': 'Tool target marker transition and closed menu verified.', 'tool_hit_verified': 'Visible tool target marker setting verified.', 'scroll_options': 'Finding the game view settings.', 'observed_zoom': 'Verifying the visible view settings.', 'zoom_minus': 'Adjusting the isolated copy zoom.', 'view_prepared': 'Supported view verified; inspecting the farmer before movement.'}[action]
        steps.append({'screenshot':str(path), 'action':action, **values})
        (root/'view-setting-preparation.json').write_text(json.dumps(result,indent=2))
    def send(window, *, point=None):
        authority()
        driver.expected_pointer_window = window
        try:
            driver.arm()
            if point is None:
                driver.send(InputCommand(InputKind.KEYBOARD,'escape','press',200,purpose='approved_view_settings'))
            else:
                target = (window.bounds[0]+point[0],window.bounds[1]+point[1])
                driver.send(InputCommand(InputKind.MOUSE,'move','move',0,target=target,purpose='approved_view_settings'))
                authority()
                driver.send(InputCommand(InputKind.MOUSE,'left_button','click',100,target=target,purpose='approved_view_settings'))
            authority()
            driver.send(InputCommand(InputKind.MOUSE,'move','move',0,
                target=(window.bounds[0]+1300,window.bounds[1]+400),purpose='approved_view_settings'))
        finally:
            driver.neutralize()
        cancel.wait(.25)
        authority()
    window, path, image = observe()
    record(path,'open_menu')
    send(window)
    window, path, image = observe()
    icon_box = (350,130,1050,205)
    icon = features.locate(image,'options-icon',icon_box)
    if icon is None:
        raise StardewAdapterError('The visible Options tab is not independently recognized')
    window, path, fresh = observe()
    if features.locate(fresh,'options-icon',icon_box) != icon:
        raise StardewAdapterError('The Options tab changed before input')
    result['menu_open_observed'] = True
    record(path,'options_tab')
    send(window,point=(icon[0]+19,icon[1]+18))
    window, path, image = observe()
    label_box = (400,215,1150,740)
    label = features.locate(image,'tool-hit-label',label_box)
    if label is None:
        raise StardewAdapterError('The visible tool hit location option is not recognized')
    def marker_state(image, label):
        box = (label[0]-50,label[1]-8,label[0],label[1]+44)
        states = [(state,features.locate(image,name,box)) for state,name in
                  ((True,'checkbox-checked'),(False,'checkbox-unchecked'))]
        matches = [(state,point) for state,point in states if point is not None]
        if len(matches) != 1:
            raise StardewAdapterError('The tool target marker checkbox state is ambiguous')
        return matches[0]
    checked, checkbox = marker_state(image,label)
    if checked != tool_marker:
        window, fresh_path, fresh = observe()
        if (features.locate(fresh,'tool-hit-label',label_box) != label
                or marker_state(fresh,label) != (checked,checkbox)):
            raise StardewAdapterError('The tool target marker option changed before input')
        record(fresh_path,'tool_hit_changed',enabled=tool_marker)
        send(window,point=(checkbox[0]+18,checkbox[1]+18))
        window, path, image = observe()
        if (features.locate(image,'tool-hit-label',label_box) != label
                or marker_state(image,label)[0] != tool_marker):
            raise StardewAdapterError('The expected tool target marker state was not observed')
    record(path,'tool_hit_verified',enabled=tool_marker)
    if marker_only:
        send(window)
        window, path, image = observe()
        if features.locate(image,'options-icon',icon_box) is not None:
            raise StardewAdapterError('The marker settings menu did not close; inspect before fresh review')
        result['menu_closed_verified'] = True
        record(path,'tool_hit_ready',enabled=tool_marker)
        return
    ui_verified = False
    previous_zoom = None
    zoom_changes = 0
    previous_panel = None
    stalled = 0
    for _ in range(40):
        window, path, image = observe()
        ui = features.locate(image,'ui-label',(535,215,790,755))
        if ui is not None:
            if features.percentage(image,ui) != 100:
                raise StardewAdapterError('This view requires independently visible UI Scale 100%')
            ui_verified = True
        zoom = features.locate(image,'zoom-label',(535,215,790,755))
        if zoom is not None:
            value = features.percentage(image,zoom)
            if not ui_verified:
                raise StardewAdapterError('UI scale was not visibly verified before zoom normalization')
            if previous_zoom is not None and value != previous_zoom-5:
                raise StardewAdapterError('The expected visible zoom decrease did not occur')
            record(path,'observed_zoom',zoom_percent=value,ui_percent=100)
            if value == 75:
                send(window)
                record(path,'view_prepared',zoom_percent=75,ui_percent=100)
                return
            if zoom_changes >= 5:
                raise StardewAdapterError('Display normalization reached its finite change budget')
            minus_box = (zoom[0]-185,zoom[1],zoom[0]-159,zoom[1]+32)
            if not features.alignments['minus'].template.matches(image.crop(minus_box)):
                raise StardewAdapterError('The enabled Zoom minus control is not recognized')
            window, fresh_path, fresh = observe()
            if (features.locate(fresh,'zoom-label',(535,215,790,755)) != zoom
                    or features.percentage(fresh,zoom) != value
                    or not features.alignments['minus'].template.matches(fresh.crop(minus_box))):
                raise StardewAdapterError('Zoom controls changed before input')
            record(fresh_path,'zoom_minus',prior_percent=value)
            send(window,point=(zoom[0]-172,zoom[1]+16))
            previous_zoom = value
            zoom_changes += 1
        else:
            panel = image.crop((350,215,1170,755)).tobytes()
            stalled = stalled+1 if panel == previous_panel else 0
            previous_panel = panel
            if stalled >= 3:
                raise StardewAdapterError('The Options menu did not scroll; no further input sent')
            arrow_box = (1200,720,1270,790)
            arrow = features.locate(image,'scroll-down',arrow_box)
            if arrow is None:
                raise StardewAdapterError('The Options scrollbar is not independently recognized')
            window, fresh_path, fresh = observe()
            if features.locate(fresh,'scroll-down',arrow_box) != arrow:
                raise StardewAdapterError('The Options scrollbar changed before input')
            record(fresh_path,'scroll_options')
            send(window,point=(arrow[0]+16,arrow[1]+16))
    raise StardewAdapterError('Display preparation reached its finite observation budget')
