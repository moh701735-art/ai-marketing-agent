const fs=require('fs');const core=fs.readFileSync('core.js','utf8');
const camps=[{campaign_id:'111',name:'boost',platform:'tiktok',client:'A'}];
const base={chat:'9',from:'9',camps,clients:[{phone:'9',client:'A',tiktok_advertiser_id:'7693'}],existing:[]};
function run(nowBaghdad,sch){const real=Date.now;Date.now=()=>Date.parse(nowBaghdad+':00Z')-3*3600e3;
 try{return new Function('$input',core)({first:()=>({json:{...base,mode:'intake',ai:{action:'schedule',campaign_name:'boost',schedule:sch}}})}).map(x=>x.json).filter(x=>x.kind==='row').map(x=>`${x.action} ${x.repeat} ${x.run_date} ${x.time}`)}finally{Date.now=real}}
const on=(t,r='once',d='')=>({action:'on',time:t,repeat:r,day:d}),off=(t,r='once',d='')=>({action:'off',time:t,repeat:r,day:d});
for(const now of ['2026-10-22T14:00','2026-10-22T03:00','2026-10-22T23:50']){
 console.log('NOW',now);
 console.log(' on6/off0 :',run(now,[on('06:00'),off('00:00')]));
 console.log(' off1/on7 :',run(now,[off('01:00'),on('07:00')]));
 console.log(' now/off 1:',run(now,[on('now'),off('01:00')]));
 console.log(' on 6:30/off 22:15:',run(now,[on('6:30'),off('22:15')]));
 console.log(' daily 6/0:',run(now,[on('06:00','daily'),off('00:00','daily')]));
 console.log(' tomorrow10:',run(now,[on('10:00','once','tomorrow'),off('18')]));
}
