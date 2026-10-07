"""Display feature/authority contracts; these do not qualify native gameplay."""
from types import SimpleNamespace
import threading

import numpy as np
import pytest
from PIL import Image

from smb3_agent.stardew_adapter import StardewAdapterError
from smb3_agent.stardew_view_settings import ViewSettingFeatures, normalize_view


def test_unknown_or_ambiguous_visible_percentage_is_not_a_setting_value():
    features = ViewSettingFeatures.__new__(ViewSettingFeatures)
    features.ink = (32,18,33)
    features.images = {}
    for value in range(75,101,5):
        rgba = np.zeros((41,105,4),dtype='uint8')
        rgba[0:value-74,0,3] = 255
        features.images[f'percent-{value}'] = Image.fromarray(rgba)
    image = Image.new('RGB',(600,100),'white')
    image.paste(features.ink,(395,0,396,1))
    assert features.percentage(image,(550,0)) == 75
    changed = image.copy()
    changed.paste(features.ink,(400,10,401,11))
    with pytest.raises(StardewAdapterError,match='not independently recognized'):
        features.percentage(changed,(550,0))
    features.images['percent-80'] = features.images['percent-75']
    with pytest.raises(StardewAdapterError,match='not independently recognized'):
        features.percentage(image,(550,0))


def test_cancel_during_display_capture_prevents_the_pending_menu_input(tmp_path,monkeypatch):
    monkeypatch.setattr('smb3_agent.stardew_view_settings.ViewSettingFeatures',lambda: object())
    cancel = threading.Event()
    commands = []
    def capture(window,path):
        Image.new('RGB',(1512,949)).save(path)
        cancel.set()
        return path
    native = SimpleNamespace(detect_window=lambda: SimpleNamespace(bounds=(0,33,1512,949)),capture=capture)
    driver = SimpleNamespace(arm=lambda:commands.append('arm'),send=lambda _:commands.append('send'))
    def authority():
        if cancel.is_set():
            raise StardewAdapterError('canceled')
    with pytest.raises(StardewAdapterError,match='canceled'):
        normalize_view(native,driver,isolation=lambda _:None,authority=authority,
                       root=tmp_path,cancel=cancel,result={})
    assert commands == []


@pytest.mark.parametrize('initially_checked,works,cancel_at,expected,desired,marker_only,close_works', [
    (False,True,None,'enabled',True,False,True), (True,True,None,'already_enabled',True,False,True),
    (False,False,None,'failed_effect',True,False,True), (False,True,5,'canceled',True,False,True),
    (False,True,None,'already_disabled',False,False,True), (True,True,None,'disabled',False,False,True),
    (True,False,None,'failed_effect',False,False,True),
    (False,True,None,'enabled',True,True,True), (False,True,None,'failed_close',True,True,False)])
def test_tool_marker_requires_current_checkbox_and_verified_effect(
        tmp_path,monkeypatch,initially_checked,works,cancel_at,expected,desired,marker_only,close_works):
    state = {'checked':initially_checked,'captures':0,'clicks':0,'menu':False,'escapes':0}
    cancel = threading.Event()
    class Features:
        def locate(self,image,name,box):
            if name == 'options-icon':
                return (900,150) if image.getpixel((1,0))[0] else None
            if name == 'tool-hit-label':
                return (500,500)
            checked = image.getpixel((0,0))[0] == 1
            if name == 'checkbox-checked':
                return (457,500) if checked else None
            if name == 'checkbox-unchecked':
                return None if checked else (457,500)
            return {'ui-label':(600,400),'zoom-label':(600,500)}.get(name)
        def percentage(self,image,label):return 100 if label[1] == 400 else 75
    monkeypatch.setattr('smb3_agent.stardew_view_settings.ViewSettingFeatures',Features)
    def capture(window,path):
        state['captures'] += 1
        image = Image.new('RGB',(1512,949))
        image.putpixel((0,0),(int(state['checked']),0,0))
        image.putpixel((1,0),(int(state['menu']),0,0))
        image.save(path)
        if state['captures'] == cancel_at:
            cancel.set()
        return path
    def send(command):
        if command.control == 'escape':
            state['escapes'] += 1
            if state['escapes'] == 1 or close_works:
                state['menu'] = not state['menu']
        if command.control == 'left_button' and command.target == (475,551):
            state['clicks'] += 1
            if works:
                state['checked'] = not state['checked']
    def authority():
        if cancel.is_set():
            raise StardewAdapterError('canceled')
    native = SimpleNamespace(detect_window=lambda:SimpleNamespace(bounds=(0,33,1512,949)),capture=capture)
    driver = SimpleNamespace(arm=lambda:None,send=send,neutralize=lambda:None)
    result = {}
    if expected in {'failed_effect','canceled','failed_close'}:
        with pytest.raises(StardewAdapterError,match='not observed|canceled|did not close'):
            normalize_view(native,driver,isolation=lambda _:None,authority=authority,
                root=tmp_path,cancel=cancel,result=result,tool_marker=desired,marker_only=marker_only)
        if expected != 'failed_close':
            assert not any(v['action']=='tool_hit_verified' for v in result.get('view_setting_steps',[]))
        assert not result.get('menu_closed_verified')
    else:
        normalize_view(native,driver,isolation=lambda _:None,authority=authority,
            root=tmp_path,cancel=cancel,result=result,tool_marker=desired,marker_only=marker_only)
        assert any(v['action']=='tool_hit_verified' and v['enabled'] == desired for v in result['view_setting_steps'])
        if marker_only:
            assert result['menu_closed_verified'] and not state['menu']
    assert state['clicks'] == (0 if expected in {'already_enabled','already_disabled','canceled'} else 1)
