"""Bounded visual Mario segment and cartridge-compatible descriptive coaching."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from smb3_agent.companion_ai import STRING, closed_schema

CONTRACT = 'smb3/world-1-1/adaptive-segment/v1'
TARGET_X = 700
MAX_DECISIONS = 32
MAX_SECONDS = 480
SCHEMA = closed_schema({
    'skill': {'type': 'string', 'enum': ['hop', 'retreat_hop', 'walk_right', 'land_right', 'retreat', 'run_hop', 'run_right', 'build_run', 'wait', 'land_run_right', 'inspect', 'stop']},
    'frames': {'type': 'integer', 'minimum': 1, 'maximum': 48},
    'delay_frames': {'type': 'integer', 'minimum': 0, 'maximum': 12},
    'reason': STRING, 'expected_effect': STRING, 'guidance_id': STRING,
})
LANGUAGE_RULES = (
    ' Mario also supports a bounded adaptive World 1-1 segment to x=700, grounded, beyond the opening, '
    'using the canonical command play the early segment. The gameplay model observes a current NES image '
    'and native state, composes jumps, walks, landing and retreat, and handles visible obstacles. '
    'Keep requested route/progress and coaching preferences in constraints. No full-level success is implied. '
    'Use interaction=coaching or correction for a requested reusable tactic. Fresh requests override conflicting memory. '
    'Remembered strategy guidance is descriptive and requires fresh Review/Start. Questions about guidance grant no input.'
)
GUIDANCE = {
    'objective': 'Reach x >= 700 in World 1-1 while alive and grounded, then release control.',
    'skills': {
        'retreat_hop': 'Grounded left+A jump, no B or delay, hold 1..26 frames; lifts off immediately while braking rightward momentum. Observe airborne effects; retreat can then reverse motion and land left of a nearby approaching hazard.',
        'hop': 'Move right, delay 0..12 frames then hold A for 1..26 frames; no B. Grounded only.',
        'walk_right': 'Move right without jumping for 1..48 frames.',
        'run_right': 'Ground positioning with right+B for 1..48 frames; accelerates for jump range. Avoid walking into hazards.',
        'build_run': 'Grounded right+B run-up for at most 1..48 frames; yield early when native rightward speed reaches 40/16 pixels per frame. Observe achieved speed before choosing a jump. Requires visible clear runway; cannot pass a wall or hazard automatically.',
        'run_hop': 'Grounded right+B jump, delay 0..12 then A hold 1..26 frames. Momentum increases range; B remains held during this skill.',
        'land_run_right': 'Airborne right+B without A, until first ground or at most 48 frames; maintains run momentum across the arc.',
        'land_right': 'If airborne, move right without A/B until grounded or at most 48 frames, then observe.',
        'retreat': 'Move left without A/B for 1..48 frames to reposition; no route reset.',
        'wait': 'Grounded neutral input for 1..48 game frames, no delay. Observe moving projectiles or plant cycles without walking into them; then choose again. Inspect freezes time and cannot show motion.',
        'inspect': 'Re-read paused native state; no movement. frames=1, delay_frames=0.',
        'stop': 'Release control without claiming arrival. frames=1, delay_frames=0.',
    },
    'mechanics': 'B accelerates horizontal movement; speed already achieved at takeoff affects jump clearance and range. Merely holding B during a jump from low or leftward speed does not establish running takeoff. Use build_run on visibly clear ground, then check vx before run_hop. Grounded retreat alone can drift right during braking and let an approaching enemy hit you before reversal. If a nearby ground hazard leaves insufficient braking room, choose an immediate retreat_hop or forward obstacle jump instead of blindly retreating; corroborate enemy height and clearance with the image. After a retreat, first reverse leftward momentum on clear runway. Launch before reaching the obstacle; an immediate jump from ground beside a tall occupied pipe may be too low even with a long hold. Raised block tops provide useful elevated launch positions. If the arc missed a block, observe the actual landing and reposition for the block rather than assuming a ground launch can clear its adjacent occupied pipe. vx/vy are signed sixteenths of a pixel per frame; negative vy means rising, positive means falling. Native y is the engine position reference, not the small visible sprite top. In this supported small-form scene the sprite is about 16 pixels below y-scroll_y, with feet about y+32; corroborate clearance with the image instead of assuming exact collision geometry. Screen y=y-scroll_y; distinguish the colorful rectangular raised blocks with corner bolts from green pipes. Raised block tops are useful intermediate landing surfaces. A predicted landing beyond a pipe is not observed traversal; check x, ground contact and the fresh image before declaring it passed. Some visible pipe plants shoot moving fireballs. Main active-object slots do not include all projectiles; special-object records separately provide raw IDs, relative x modulo 256 and native y. Corroborate these with the image; type and velocity are not inferred from a raw ID. A shot can hit a raised-block launch far left of its plant. Check the actual projectile path before jumping; safe plant separation alone is insufficient. Use short grounded neutral wait intervals to let an approaching overhead shot pass and observe again before takeoff. Never assume a block-top landing or rising arc makes projectile contact safe. Native active object x/y are top positions, not landing surfaces; object IDs are raw cartridge values, not verified type names. Treat unknown active objects near the path as hazards and corroborate with the image. Pipe-mounted plants cannot safely be stomped; do not descend onto an occupied pipe. Holding A against a ceiling can truncate the arc. A short walk-speed hop followed by 48 frames of blind drift may land into a plant; choose run momentum, clearance and shorter observation intervals where needed. dying!=0 is an unsafe animation, never a successful bounce or safe ground; air=0 alone does not establish alive. Higher jumps require longer A hold. Use the current image for blocks, pipes, enemies and ground. Image coordinates are NES pixels; x/y are world coordinates, screen x=x-scroll_x and screen y=y-scroll_y. Treat uncertain objects as hazards, not guaranteed rewards. A grounded state can be on a block or pipe. Never hold jump continuously across landings.',
    'rules': 'Choose the next skill from current state, terrain and goal. Predict a checkable effect; compare prior effects before deciding again. Use retreat to obtain jump clearance when blocked. land_right stops at the first grounded observation; walking is useful for positioning. Current observations and current player constraints override remembered guidance. Set guidance_id to the compatible remembered row used for this decision, or empty string; naming it records requested application, not improved outcome. Do not invent terrain or infer success from your prediction. Review/Start authorizes this scope, while the native controller owns frame timing and input. No purchases, flight, resets, entry to pipes or complete-level claims.',
    'limits': '32 decisions, 1200 input frames and 480 wall seconds per attempt; existing reviewed maximum attempts and 600-second retry expiry remain. Stop on death, changed scene, invalid boundary, missing image, repeated lack of grounded progress or any exhausted budget. Coins are observed but complete coverage and rewards remain unknown.',
}


def expand_plan(plan):
    plan['strategy_contract'] = CONTRACT
    plan['path_choice'] = 'adaptive_segment'
    plan['stop_point'] = 'world_1_1_segment_end'
    parameters = plan['actions'][0]['parameters']
    parameters.update(path_choice='adaptive_segment', stop_point='world_1_1_segment_end',
                      primitive_id='world_1_1_adaptive_segment_v1')
    plan['fallback_explanation'] = 'Experimental bounded visual strategy. Full-level completion, rewards and improved reliability remain unknown.'
    plan['change_summary'] = ['Model-directed World 1-1 segment to x >= 700, alive and grounded. The model composes jumps, walks, landing and retreat from fresh images and effects. Each attempt has 32 decisions, 1200 skill frames and 480 seconds; the displayed finite attempt budget remains.']


def remember(store, intent, original, cartridge):
    data = store.read()
    for row in data['coaching']:
        if row.get('kind') == 'strategy' and row.get('status') == 'active':
            row['status'] = 'superseded'
    row = {'id': uuid4().hex, 'kind': 'strategy', 'status': 'active',
           'original_words': original, 'constraints': deepcopy(intent['constraints']),
           'compatibility': CONTRACT, 'cartridge_sha256': cartridge,
           'objective_context': intent['objective'], 'application': 'next_compatible_attempt',
           'improvement_observed': None}
    data['coaching'].append(row)
    store.write(data)
    return row


def compatible_guidance(rows, cartridge):
    active = [r for r in rows if r.get('kind') == 'strategy' and r.get('status') == 'active']
    compatible = [deepcopy(r) for r in active if r.get('compatibility') == CONTRACT and cartridge and r.get('cartridge_sha256') == cartridge]
    incompatible = [r['id'] for r in active if r not in compatible]
    return compatible, incompatible


def boundary_image(service, boundary):
    from smb3_agent.fceux_images import load_gd_screenshot
    live = service.live_manager.snapshot()
    root = Path(live.artifact_dir) / 'state-samples'
    source = root / f"{int(boundary['frame']):09d}_strategy_{int(boundary['boundary_id'])}.gd"
    destination = source.with_suffix('.png')
    load_gd_screenshot(source).save(destination)
    return destination


def observed_state(boundary):
    """Native facts only; image interpretation and predicted effects stay separate."""
    objects = []
    for slot in range(1, 10):
        prefix = f'object_{slot}_'
        if prefix + 'state' in boundary:
            objects.append({k: int(boundary[prefix+k]) for k in ('x', 'y', 'state', 'id')} | {'slot': slot})
    specials=[{'slot':i, 'id':int(boundary[f'special_{i}_id']), 'relative_x_modulo_256':int(boundary[f'special_{i}_dx']), 'y':int(boundary[f'special_{i}_y'])} for i in range(8) if f'special_{i}_id' in boundary]
    return {'provenance': 'native RAM at frozen boundary',
            'unsafe_animation': int(boundary.get('dying', 0)) != 0,
            'ground_contact': int(boundary.get('air', 1)) == 0,
            'horizontal_pixels_per_frame': int(boundary.get('vx', 0))/16,
            'vertical_pixels_per_frame': int(boundary.get('vy', 0))/16,
            'active_objects': objects, 'special_objects': specials,
            'special_position_limits': 'Relative x wraps to -128..127; corroborate the image. Type and velocity remain unknown.',
            'terrain': 'Interpret current image; native object records are not terrain.',
            'predictions': 'Unknown until a subsequent observation confirms them.'}
