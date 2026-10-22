const fs=require('fs');
const lib=fs.readFileSync('lib.js','utf8');
const run=(file,ctx,sub={})=>{let code=fs.readFileSync(file,'utf8').replace('//__LIB__',lib);for(const k in sub)code=code.replace(k,sub[k]);return new Function('$','$json','$input',code)(ctx.$,ctx.json,ctx.input);};
const mk=(map)=>(n)=>{if(!map[n])throw new Error('no node '+n);return {first:()=>map[n][0],all:()=>map[n]};};
const camps=[{campaign_id:'111',name:'boostpro7889',platform:'tiktok',client:'A',status:'ACTIVE'},{campaign_id:'222',name:'شامبو',platform:'meta',client:'B'}];
const base={'قراءة رسالة تليجرام':[{json:{chatId:'999'}}],'تجهيز سياق الـAI':[{json:{campaignHistory:camps,from:'999'}}],'جلب العملاء (للـAI)':[{json:{phone:'999',client:'A',tiktok_advertiser_id:'7693'}}],'جلب الأحداث':[]};
const names={'جدولة: الأحداث الحالية':[]};
const t=(ai,ev=[])=>run('intake.js',{$:mk({...base,'استخراج نتيجة الـAI1':[{json:ai}],'جدولة: الأحداث الحالية':ev.map(json=>({json}))}),json:ai});
let o;
o=t({action:'schedule',campaign_name:'boostpro',schedule:[{action:'on',time:'01:00',repeat:'daily'},{action:'off',time:'07:00',repeat:'daily'}]});
console.log(JSON.stringify(o.map(x=>[x.json.kind,x.json.action,x.json.repeat,x.json.time,x.json.run_date,x.json.last_run_date])), '\n', o[0].json.finalMessage);
o=t({action:'schedule',campaign_name:'شامبو',schedule:[{action:'on',time:'now'},{action:'off',time:'01:00'}]});
console.log(JSON.stringify(o.map(x=>[x.json.action,x.json.repeat,x.json.time,x.json.run_date])), '\n', o[0].json.finalMessage);
o=t({action:'schedule',campaign_name:'zzz',schedule:[]}); console.log(o[0].json.finalMessage);
o=t({action:'schedule_list'},[{sid:'S1',phone:'999',status:'active',campaign_id:'111',campaign_name:'boostpro7889',platform:'tiktok',action:'on',repeat:'daily',time:'01:00'}]); console.log(o[0].json.finalMessage);
o=t({action:'schedule_cancel',campaign_name:'boostpro'},[{sid:'S1',phone:'999',status:'active',campaign_id:'111',campaign_name:'boostpro7889',platform:'tiktok',action:'on',repeat:'daily',time:'01:00'}]); console.log(o[0].json.status,o[0].json.finalMessage);
// due
const B=new Date(Date.now()+3*3600e3);const d=B.toISOString().slice(0,10),h=B.toISOString().slice(11,16);
const rows=[{sid:'a',status:'active',repeat:'once',run_date:d,time:'00:00',campaign_id:'1',platform:'tiktok',action:'on'},{sid:'b',status:'active',repeat:'once',run_date:d,time:h,campaign_id:'1',platform:'tiktok',action:'off'},{sid:'c',status:'active',repeat:'daily',last_run_date:'',time:'00:00',campaign_id:'2',platform:'meta',action:'on'},{sid:'d',status:'active',repeat:'once',run_date:'2999-01-01',time:'00:00',campaign_id:'3'}];
o=run('due.js',{$:mk({}),json:{},input:{all:()=>rows.map(json=>({json}))}});console.log(JSON.stringify(o.map(x=>[x.json.sid,x.json.api,x.json.skipReason])));
// result
const src=[{json:{sid:'b',status:'active',repeat:'once',platform:'tiktok',action:'off',campaign_name:'x',phone:'9',api:'apply',time:h,last_result:''}}];
const resCode=fs.readFileSync('result.js','utf8').replace('__SRC__',"$('IFT').all()");
let r1=new Function('$','$input',resCode)(mk({IFT:src}),{all:()=>[{json:{code:40001,message:'No permission'},pairedItem:{item:0}}]});console.log(JSON.stringify(r1[0].json));
r1=new Function('$','$input',resCode)(mk({IFT:src}),{all:()=>[{json:{code:0},pairedItem:{item:0}}]});console.log(JSON.stringify(r1[0].json));
const skipCode=fs.readFileSync('result.js','utf8').replace('__SRC__',"null");
r1=new Function('$','$input',skipCode)(mk({}),{all:()=>[{json:{...src[0].json,api:'skip',skipReason:'superseded'}}]});console.log(JSON.stringify(r1[0].json));
