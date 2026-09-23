// 23a - Split Team Numbers: one WhatsApp message per team member number
const j = $input.first().json;
return (j.team_numbers || []).map(n => ({ json: { to: n, text: j.team_message } }));
