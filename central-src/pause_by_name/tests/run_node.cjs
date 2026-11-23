// usage: node run_node.cjs <bodyfile> <ctxjson>  -> prints JSON of the node's return value
const fs = require('fs');
const body = fs.readFileSync(process.argv[2], 'utf8'); const c = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const $ = (n) => ({ first: () => ({ json: (c.nodes || {})[n] }), all: () => [{ json: (c.nodes || {})[n] }] });
const $input = { first: () => ({ json: c.input }), all: () => (c.inputs || [c.input]).map(j => ({ json: j })) };
const fn = new Function('$', '$input', body);
console.log(JSON.stringify(fn($, $input)));
