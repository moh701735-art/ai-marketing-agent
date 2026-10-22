const items = $('__RES__').all().filter(i => i.json.notify);
return items.map(i => ({ json: { phone: i.json.phone, text: i.json.finalMessage } }));
