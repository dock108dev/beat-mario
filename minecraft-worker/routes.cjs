'use strict'
const {Vec3}=require('vec3')
const point=p=>new Vec3(p.x,p.y,p.z)
function pathLength(start,path) {
 let previous=point(start), total=0
 for(const p of path){total+=previous.distanceTo(point(p));previous=point(p)}
 return total
}
function route(bot,from,target,args={}) {
 const {goals}=require('mineflayer-pathfinder')
 const goal=args.exact_target?new goals.GoalBlock(Math.floor(target.x),Math.floor(target.y),Math.floor(target.z)):new goals.GoalNear(Math.floor(target.x),Math.floor(target.y),Math.floor(target.z),1)
 const iterator=bot.pathfinder.getPathFromTo(bot.pathfinder.movements,point(from),goal,{timeout:160,tickTimeout:160,searchRadius:32,optimizePath:false})
 const first=iterator.next().value?.result
 iterator.return?.()
 if(first?.status!=='success')return {known:false,reason:first?.status||'unknown'}
 const path=first.path||[]
 if(args.goal_origin && path.some(p=>point(p).distanceTo(point(args.goal_origin))>31.5))return {known:false,reason:'outside_parent_bounds'}
 if(path.some(p=>p.toBreak?.length||p.toPlace?.length||p.parkour))return {known:false,reason:'unsupported_path'}
 return {known:true,length:pathLength(point(from).floored(),path),target,steps:path.length}
}
function reservation(outbound,back,used,budget=192) {
 if(!outbound.known||!back.known)return {allowed:false,reason:'return_route_unknown'}
 const reserve=Math.ceil(back.length*1.5)+8
 return {allowed:used+Math.ceil(outbound.length*1.35)+reserve+6<=budget,reserve,outbound:outbound.length,return_length:back.length,used,budget,reason:'return_reserve_required'}
}
function select(bot,targets,args,used=0) {
 let rejected=[], choices=[]
 for(const target of targets.slice(0,12)) {
  const out=route(bot,bot.entity.position,target,args)
  if(!out.known){rejected.push({target,reason:'outbound_'+out.reason});continue}
  const back=args.return_target&&!args.returning?route(bot,target,args.return_target,{...args,exact_target:false}):{known:true,length:0}
  const cost=args.return_target&&!args.returning?reservation(out,back,used,args.travel_budget||192):{allowed:used+out.length*1.35+4<=(args.travel_budget||192),reserve:0,reason:'travel_budget_required'}
  if(!cost.allowed){rejected.push({target,reason:cost.reason});continue}
  choices.push({...out,...cost})
 }
 choices.sort((a,b)=>a.length-b.length)
 if(!choices.length)throw Error(rejected.some(r=>r.reason==='return_reserve_required')?'return_reserve_required':rejected.some(r=>r.reason==='return_route_unknown')?'return_route_unknown':'no_complete_observed_route: '+rejected.map(r=>r.reason).join(','))
 return {...choices[0],rejected}
}
function oscillating(samples) {
 if(samples.length<2)return false
 const first=samples[0],last=samples[samples.length-1]
 return last.at-first.at>=2500 && last.travel-first.travel>6 && point(first.position).distanceTo(point(last.position))<1.5
}
module.exports={pathLength,route,reservation,select,oscillating}

function blockedStep(path,position) {
 if(!path.length)return null
 let nearest=0
 for(let i=1;i<path.length;i++)if(point(path[i]).distanceTo(position)<point(path[nearest]).distanceTo(position))nearest=i
 if(point(path[nearest]).floored().equals(point(position).floored()))nearest++
 return nearest<path.length?point(path[nearest]).floored():null
}
module.exports.blockedStep=blockedStep
