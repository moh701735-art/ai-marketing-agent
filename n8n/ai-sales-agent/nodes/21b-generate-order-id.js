// 21b - Generate Order ID: unique, sequential, derived from the database row id (ORD-YYYY-000123)
const row = $input.first().json || {};
if (!row.id) throw new Error('ORDER_INSERT_RETURNED_NO_ID');
const year = new Date().toLocaleString('en-US', { timeZone: 'Asia/Baghdad', year: 'numeric' });
return [{ json: { row_id: row.id, order_id: 'ORD-' + year + '-' + String(row.id).padStart(6, '0') } }];
