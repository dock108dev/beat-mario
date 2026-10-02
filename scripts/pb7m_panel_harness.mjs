// Retained ordinary UI harness. Every camera authority action uses visible controls.
export function createHarness(panel, fs, root, index) {
  return {
    panel, fs, root, index,
    async details() { return JSON.parse(await this.panel.playwright.locator('#camera-details').innerText()); },
    async save() { await this.fs.writeFile(this.root+'/qualification-ui-index.json',JSON.stringify(this.index,null,2)); },
    async retain(label,purpose,initial=null) {
      const snapshot=await this.panel.playwright.domSnapshot(), d=await this.details();
      const history=d.result.evidence_path, r=JSON.parse(await this.fs.readFile(history,'utf8'));
      await this.fs.writeFile(this.root+'/'+label+'.txt',snapshot);
      await this.fs.writeFile(this.root+'/'+label+'.png',await this.panel.screenshot({fullPage:true}));
      const e={label,purpose,ui_snapshot:this.root+'/'+label+'.txt',ui_screenshot:this.root+'/'+label+'.png',history,attempt_id:r.attempt_id,status:r.result.status,initial:r.initial?[r.initial.heading,r.initial.pitch]:null,result:r.result};
      if(purpose==='core') {
        e.pass=r.candidate===this.index.candidate&&r.result.status==='verified_completion'&&r.result.neutral_handback_confirmed&&Math.max(...r.result.sampled_residual_view_change.map(Math.abs))<=.1&&r.release.seconds<=.3&&(!initial||Math.max(Math.abs((r.initial.heading-initial[0]+540)%360-180),Math.abs(r.initial.pitch-initial[1]))<=.15);
        this.index.core.push(e);
      } else this.index.excluded.push(e);
      await this.save();
      if(e.pass===false)throw Error('Frozen core gate failed; group stops');
      return e;
    },
    async start(heading,pitch,label='fault') {
      this.oldResult=(await this.details()).result?.evidence_path;
      await this.panel.playwright.getByLabel('Heading (−180° to 180°)').fill(String(heading));
      await this.panel.playwright.getByLabel('Pitch (−90° to 90°)').fill(String(pitch));
      await this.panel.playwright.domSnapshot();
      await this.panel.playwright.locator('#camera-review').click();
      await this.panel.playwright.locator('#camera-start').click({timeoutMs:6000});
      await this.fs.writeFile(this.root+'/'+label+'-started.txt',await this.panel.playwright.domSnapshot());
    },
    async waitResult(label,purpose='native_fault_raw',initial=null) {
      const deadline=Date.now()+25000;
      while(Date.now()<deadline) {
        const d=await this.details();
        if(d.result?.evidence_path&&d.result.evidence_path!==this.oldResult&&await this.panel.playwright.locator('#camera-review').isEnabled())return this.retain(label,purpose,initial);
        await this.panel.playwright.waitForTimeout(100);
      }
      throw Error('Ordinary UI outcome timeout; inspect retained attempt before continuing');
    },
    async goal(label,heading,pitch,purpose='core',initial=null) {
      await this.start(heading,pitch,label);return this.waitResult(label,purpose,initial);
    },
    async control(label,button,heading,pitch) {
      const before=new Set(await this.fs.readdir(this.root+'/../runs'));await this.start(heading,pitch,label);
      let delivery=null;const deadline=Date.now()+12000;
      while(Date.now()<deadline) {
        for(const id of await this.fs.readdir(this.root+'/../runs')) {
          if(before.has(id))continue;let rows=[];
          try{rows=(await this.fs.readFile(this.root+'/../runs/'+id+'/native-motion.jsonl','utf8')).trim().split('\n').map(JSON.parse);}catch{}
          if(rows.some(r=>r.kind==='delivered')){delivery={run:id,rows,observed_wall_ms:Date.now()};break;}
        }
        if(delivery)break;await this.panel.playwright.waitForTimeout(2);
      }
      if(!delivery)throw Error('No correction delivery before control; retain fixture miss');
      await this.panel.playwright.getByRole('button',{name:button,exact:true}).click();
      const snapshot=await this.panel.playwright.domSnapshot();
      const ack=JSON.parse(await this.panel.playwright.locator('#camera-practice').getAttribute('data-control-acknowledgment'));
      await this.fs.writeFile(this.root+'/'+label+'-control.json',JSON.stringify({delivery,ack,snapshot},null,2));
      const e=await this.waitResult(label),r=JSON.parse(await this.fs.readFile(e.history,'utf8'));
      e.control_ack=ack;e.pass=r.candidate===this.index.candidate&&r.result.status!=='verified_completion'&&r.result.neutral_handback_confirmed&&r.hid_release.confirmed&&ack.ui_ack_ms<=500&&ack.native_release.seconds<=.3&&ack.native_release.epoch_revoked&&ack.native_release.motion_worker_reaped&&Math.max(...r.result.sampled_residual_view_change.map(Math.abs))<=.1;
      this.index.faults.push(e);await this.save();if(!e.pass)throw Error('Frozen direct-control gate failed; group stops');return e;
    },
    async pending(session,heading,pitch) {
      await this.start(heading,pitch,'s'+session+'-pending');let token=null;const deadline=Date.now()+12000;
      while(Date.now()<deadline) {
        let producer=null;try{producer=JSON.parse(await this.fs.readFile(this.root+'/../session-'+session+'/faults/pending-producer.json','utf8'));}catch{}
        if(producer){let packets=[];try{packets=(await this.fs.readFile(producer.native_log.replace('native-motion.jsonl','native-requests.jsonl'),'utf8')).trim().split('\n').map(JSON.parse);}catch{}
          const packet=packets.find(x=>x.request.kind==='pulse');if(packet){token={producer,packet,observed_wall_ms:Date.now()};await this.panel.playwright.locator('#camera-stop').click();break;}}
        await this.panel.playwright.waitForTimeout(2);
      }
      if(!token)throw Error('Pending fixture did not bind; retain fixture miss');
      token.ack=JSON.parse(await this.panel.playwright.locator('#camera-practice').getAttribute('data-control-acknowledgment'));
      const e=await this.waitResult('s'+session+'-pending-emitter-cancellation'),r=JSON.parse(await this.fs.readFile(e.history,'utf8'));
      const controls=(await this.fs.readFile(this.root+'/../control-receipts.jsonl','utf8')).trim().split('\n').map(JSON.parse),cr=controls.findLast(x=>x.epoch===token.producer.epoch&&x.reason==='Stopped');
      const logs=(await this.fs.readFile(token.producer.native_log,'utf8')).trim().split('\n').map(JSON.parse);
      e.pending=token;e.cancel_receipt=cr;e.pass=!!cr&&cr.at<token.packet.request.deadline&&cr.at>token.packet.flushed_at&&token.ack.ui_ack_ms<=500&&token.ack.native_release.seconds<=.3&&r.result.neutral_handback_confirmed&&r.hid_release.confirmed&&Math.max(...r.result.sampled_residual_view_change.map(Math.abs))<=.1&&!logs.some(x=>x.kind==='delivered');
      this.index.faults.push(e);await this.save();if(!e.pass)throw Error('Frozen pending gate failed; group stops');return e;
    },
    async nativeFault(session,mode,label) {
      const root=this.root+'/../session-'+session+'/faults/',p=JSON.parse(await this.fs.readFile(root+mode+'-producer.json','utf8')),s=JSON.parse(await this.fs.readFile(root+mode+'-post-cancel/attempt.json','utf8'));
      const id=p.native_log.split('/').slice(-2)[0],history=this.root+'/../history/'+id+'.json',r=JSON.parse(await this.fs.readFile(history,'utf8'));
      const controls=(await this.fs.readFile(this.root+'/../control-receipts.jsonl','utf8')).trim().split('\n').map(JSON.parse),cr=controls.findLast(x=>x.epoch===p.epoch&&x.at>=p.fault_started_at);
      const logs=(await this.fs.readFile(p.native_log,'utf8')).trim().split('\n').map(JSON.parse),upper=(Date.parse(r.recorded_at)-p.wall_started_ns/1e6)/1000,release=cr?cr.release:r.release;
      const e={label,purpose:'native_fault',history,attempt_id:id,producer:p,post_cancel_settling:root+mode+'-post-cancel/attempt.json',control_receipt:cr??null,result:r.result,release,cancellation_path:cr?'service watchdog revoke':'correction worker finally cancel',cancel_completion_upper_bound_seconds:upper};
      e.pass=r.candidate===this.index.candidate&&r.result.status!=='verified_completion'&&release.seconds<=.3&&release.motion_worker_reaped&&release.epoch_revoked&&release.pending_motion_revoked&&r.hid_release.confirmed&&s.settled&&(cr?s.began_at>cr.at:upper<=.3)&&!logs.some(x=>x.kind==='delivered'&&x.monotonic>(cr?.at??p.fault_started_at));
      this.index.faults.push(e);await this.save();if(!e.pass)throw Error('Frozen native fault gate failed; group stops');return e;
    }
  };
}
