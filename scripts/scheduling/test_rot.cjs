const fs=require('fs');const core=fs.readFileSync('rot_core.js','utf8');
const run=(inp)=>new Function('$input',core)({first:()=>({json:inp})}).map(x=>x.json);
const dec=[{campaign_id:'1',campaign_name:'شامبو',limit:0.3,cpr:0.38,msgs:5,spend:1.9,stop:true,account_id:'55',rot:{on:1,gen:1,max:3,root:'1',used:[]}},
 {campaign_id:'2',campaign_name:'B',limit:0.3,cpr:0.5,msgs:3,spend:1.5,stop:true,rot:{on:1,gen:3,max:3}},
 {campaign_id:'3',campaign_name:'C',limit:0.3,cpr:0.5,msgs:3,spend:1.5,stop:true,rot:null}];
let o=run({mode:'rotCopy',dec,stops:[{success:true},{success:true},{success:true}]});console.log(o.map(x=>x.kind+'|'+(x.campaign_id||x.text.slice(0,30))));
const ctx=o.filter(x=>x.kind==='copy');
o=run({mode:'rotTarget',ctx,copies:[{copied_campaign_id:'99'}],adsets:[{data:[{id:'a1',targeting:{age_min:18,age_max:65,geo_locations:{countries:['IQ']},targeting_automation:{advantage_audience:1}}},{id:'a2',targeting:{age_min:18,age_max:65}}]}]});
console.log(o.map(x=>[x.kind,x.adset_id,x.bracket,JSON.stringify(x.targeting)].join('|')));
const upd=o.filter(x=>x.kind==='upd');
o=run({mode:'rotCheck',ctx:upd,res:[{success:true},{success:true}]});console.log(o);
const act=o;
o=run({mode:'rotFinal',ctx:act,res:[{success:true}]});console.log(o.map(x=>x.kind+'|'+JSON.stringify(x.row||x.text)));
o=run({mode:'rotCheck',ctx:upd,res:[{success:true},{error:{message:'bad'}}]});console.log(o[0].ok,o[0].err);
// gen2 -> next bracket
const ctx2=[{...ctx[0],gen:2,used:['18-65','25-34'],name:'شامبو - جمهور 2'}];
o=run({mode:'rotTarget',ctx:ctx2,copies:[{copied_campaign_id:'100'}],adsets:[{data:[{id:'b1',targeting:{age_min:25,age_max:34}}]}]});console.log(o[0].bracket,o[0].used);
console.log(run({mode:'rotTarget',ctx,copies:[{error:{message:'perm'}}],adsets:[{}]})[0].text);
